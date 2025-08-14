from app import app, db
from app.models import Word, Action, Category, Settings
from app.paronym.models import Sentence
from app.utils import add_action, get_strike

if app.config.get('ENABLE_TELEGRAM', False):
    from app import bot

from flask import render_template, jsonify, request, session, render_template_string, redirect
from sqlalchemy import and_, func, case
from pymorphy3.analyzer import MorphAnalyzer

import datetime
import os
import random
from secrets import token_hex


@app.route('/')
def index():
    if 'user_id' not in session and app.config.get('ENABLE_TELEGRAM', False):
        return render_template('auth.html')
    elif 'user_id' not in session and not app.config.get('ENABLE_TELEGRAM', False):
        session['user_id'] = int(10000000000000 * random.random() + 10000000000000)

    user_id = session.get('user_id')
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()

    if user_settings is None:
        user_settings = Settings(user_id=user_id)
        db.session.add(user_settings)
        db.session.commit()

    strike = session.get('strike', get_strike(user_id)) if user_settings.strike else None

    return render_template('index.html', strike=strike)


@app.route('/demo')
def demo_page():
    return render_template('index.html', strike=None, demo=True, params='demo=true')


@app.route('/get_frame')
def get_frame():
    task_id = request.args.get('task_id', '')
    category_id = request.args.get('category_id', '')
    category = Category.query.get(category_id)
    mistakes = request.args.get('mistakes', '')
    admin = session.get('admin', False)
    demo = request.args.get('demo', False)

    user_id = session.get('user_id')
    admin = (str(user_id) == str(os.getenv('ADMIN_ID'))) and admin
    if task_id == '5':
        sentence = Sentence.query.order_by(func.random()).first()
        info_str = [f'Фильтр: "Задание №{task_id}"']
        return render_template('frame_inner.html', word=sentence, info_str=info_str)

    if task_id:
        words = Word.query.filter(Word.task_number == task_id)
        info_str = [f'Фильтр: "Задание №{task_id}"']
    elif category_id:
        words = Word.query.filter(Word.category_id == category_id)
        info_str = [f'Фильтр: "Категория "{category.name}""']
    elif mistakes:
        stats = (
            db.session.query(
                Action.word_id,
                func.sum(case((Action.action == Action.WRONG_ANSWER, 1), else_=0)).label('wrong_count'),
                func.sum(case((Action.action == Action.RIGHT_ANSWER, 1), else_=0)).label('right_count')
            )
            .filter(Action.user_id == user_id)
            .group_by(Action.word_id)
            .subquery()
        )

        query = (
            db.session.query(Word)
            .join(stats, Word.id == stats.c.word_id)
            .filter(stats.c.wrong_count > stats.c.right_count)
        )

        word = query.order_by(func.random()).first()
        info_str = ['Фильтр: "Неверые ответы"']

        if word:
            return render_template('frame_inner.html', word=word, info_str=info_str)
        else:
            return 'No words available', 404
    else:
        words = Word.query
        info_str = []

    words = words.outerjoin(Action, and_(
        Word.id == Action.word_id,
        Action.user_id == user_id
    )).filter(Action.id.is_(None))

    stats = (
        db.session.query(
            Action.word_id,
            func.sum(case((Action.action == Action.WRONG_ANSWER, 1), else_=0)).label('wrong_count'),
            func.sum(case((Action.action == Action.RIGHT_ANSWER, 1), else_=0)).label('right_count')
        )
        .filter(Action.user_id == user_id)
        .group_by(Action.word_id)
        .subquery()
    )

    # Основной запрос: присоединяем статистику к Word
    difficult_words = (
        db.session.query(Word, (stats.c.wrong_count - stats.c.right_count).label('diff'))
        .join(stats, Word.id == stats.c.word_id)
        .order_by((stats.c.wrong_count - stats.c.right_count).desc())
    )

    words_len = words.count()

    difficult_words = list(set(words.all()) & set(difficult_words.all()))

    diff_word_len = len(difficult_words)
    difficult_words = difficult_words[:50]

    if (random.random() * (words_len + diff_word_len) > diff_word_len or not difficult_words) and words.count():
        print(1)
        word = words.order_by(func.random()).first()
        info_str.append('Это слово встретилось первый раз')
    elif difficult_words:
        print(2)
        word = random.choice(difficult_words)[0]
        info_str.append('Это слово встретилось из-за большого количества ошибок')
    else:
        print(3)
        word = Word.query.order_by(func.random()).first()
        info_str.append('Это слово встретилось случайно')

    if word:
        return render_template('frame_inner.html', word=word, info_str=info_str, admin=admin, demo=demo)
    else:
        return 'No words available', 404


# @app.route('/get_word')
# def word():
#     word = Word.query.order_by(db.func.random()).first()
#     return jsonify({'html_word': word.get_html(),
#                     'explanation': word.explanation,
#                     'answers': word.get_answers(),
#                     'id': word.id})


@app.route('/check_word', methods=['POST'])
def check_word():
    user_id = session.get('user_id', None)
    user_settings = Settings.query.filter(Settings.user_id == user_id).first() if user_id else None

    note_id = request.json.get('id')
    answer = request.json.get('answer')
    is_paronym = len(answer) > 2 and answer.islower()
    if not is_paronym:
        note = Word.query.get(note_id)
        if '_' in note.word:
            full_note = note.word.replace('_', note.answers[0])
        else:
            full_note = note.answers[0]
        explanation = note.explanation
        right_answer = note.answers[0]
    else:
        note = Sentence.query.get(note_id)
        parse_word = MorphAnalyzer().parse(note.word.word)[0]
        word_in_right_form = parse_word.inflect(set(note.word_tags.split(','))).word
        full_note = note.sentence.replace('_______', word_in_right_form)
        right_answer = word_in_right_form
        explanation = None

    if note and answer == right_answer:
        if user_settings and user_settings.strike:
            session['strike'] = session.get('strike', get_strike(user_id)) + 1

        if not is_paronym:
            add_action(user_id=user_id, word_id=note_id, action=Action.RIGHT_ANSWER)

        return jsonify({
            'correct': True, 'full_word': full_note, 'explanation': explanation,
            'strike': {
                'n': session.get('strike', None),
                'levels': app.config['STRIKE_LEVELS']
            }})
    else:
        if user_settings and user_settings.strike:
            session['strike'] = 0

        if not is_paronym:
            add_action(user_id=user_id, word_id=note_id, action=Action.WRONG_ANSWER)

        return jsonify({
            'correct': False, 'full_word': full_note, 'explanation': explanation,
            'strike': {
                'n': session.get('strike'),
                'levels': app.config['STRIKE_LEVELS']
            }})


@app.route('/mistake_report', methods=['POST'])
def mistake_report():
    word_id = request.json.get('id')
    word = Word.query.get(word_id)

    if word is None:
        return 'non-existent word id', 400

    word.mistake = True
    db.session.commit()

    with open('mistakes.txt', 'a', encoding='utf-8') as file:
        file.write(f'{datetime.datetime.now()} - {word.word} [{word.id}]\n')

    return 'ok', 200


@app.route('/action/swipe_next', methods=['POST'])
def action_swipe_next():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401

    user_id = session.get('user_id')
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()

    word_id = int(request.json.get('word_id'))
    user_id = session.get('user_id')
    if word_id is not None:
        last_words = Action.query.filter(Action.user_id == user_id).order_by(Action.datetime.desc()).limit(3)
        last_ids = [e.word_id for e in last_words]
        if word_id in last_ids:
            return jsonify({'status': 'success', 'strike': session.get('strike', get_strike(user_id))}), 200

        if user_settings.strike:
            session['strike'] = 0
        add_action(user_id=user_id, word_id=word_id, action=Action.SKIP)
        return jsonify({'status': 'success', 'strike': 0}), 200
    else:
        return jsonify({'status': 'error', 'error': 'no word id'}), 400


# Функции для личного пользования, скоро уберу)
@app.route(f'/{os.getenv("RED_CARD", None)}')
def red_card():
    if os.getenv("RED_CARD", None) is not None and os.getenv("RED_CARD_URL", None) is not None:
        return redirect(os.getenv("RED_CARD_URL", None), code=302)
    return 'Not found', 404


@app.route(f'/{os.getenv("BLUE_CARD", None)}')
def blue_card():
    if os.getenv("BLUE_CARD", None) is not None and os.getenv("BLUE_CARD_URL", None) is not None:
        return redirect(os.getenv("BLUE_CARD_URL", None), code=302)
    return 'Not found', 404
