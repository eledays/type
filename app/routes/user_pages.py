from app.extensions import db
from app.models import Action, Category, Sentence, Word
from app.utils import add_action, get_cached_strike

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session
from flask_login import current_user, login_required
from sqlalchemy import and_, func, case
from pymorphy3.analyzer import MorphAnalyzer

import datetime
import random


bp = Blueprint("user_pages", __name__)


@bp.route('/')
@login_required
def index():
    user = current_user
    strike = (
        get_cached_strike(user.id)
        if user.settings.strike
        else None
    )

    return render_template('index.html', strike=strike)


@bp.route('/demo')
def demo_page():
    return redirect('/')


@bp.route('/get_frame')
@login_required
def get_frame():
    task_id = request.args.get('task_id', '')
    category_id = request.args.get('category_id', '')
    category = (
        db.session.get(Category, int(category_id))
        if category_id.isdigit()
        else None
    )
    mistakes = request.args.get('mistakes', '')
    admin = session.get('admin', False)
    demo = request.args.get('demo', False)

    user = current_user
    user_id = user.id
    admin = user.is_admin and admin
    if task_id == '5':
        sentence = Sentence.query.order_by(func.random()).first()
        info_str = [f'Фильтр: "Задание №{task_id}"']
        if sentence is None:
            return 'No sentences available', 404
        return render_template('frame_inner.html', word=sentence, info_str=info_str)

    if task_id:
        base_words = Word.query.filter(Word.task_number == task_id)
        info_str = [f'Фильтр: "Задание №{task_id}"']
    elif category_id:
        if category is None:
            return 'Category not found', 404
        base_words = Word.query.filter(Word.category_id == category.id)
        info_str = [f'Фильтр: "Категория "{category.name}""']
    elif mistakes:
        stats = (
            db.session.query(
                Action.word_id,
                func.sum(
                    case((Action.action == Action.WRONG_ANSWER, 1), else_=0)
                ).label('wrong_count'),
                func.sum(
                    case((Action.action == Action.RIGHT_ANSWER, 1), else_=0)
                ).label('right_count')
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
        base_words = Word.query
        info_str = []

    unseen_words = base_words.outerjoin(Action, and_(
        Word.id == Action.word_id,
        Action.user_id == user_id
    )).filter(Action.id.is_(None))

    stats = (
        db.session.query(
            Action.word_id,
            func.sum(
                case((Action.action == Action.WRONG_ANSWER, 1), else_=0)
            ).label('wrong_count'),
            func.sum(
                case((Action.action == Action.RIGHT_ANSWER, 1), else_=0)
            ).label('right_count')
        )
        .filter(Action.user_id == user_id)
        .group_by(Action.word_id)
        .subquery()
    )

    difficulty = stats.c.wrong_count - stats.c.right_count
    difficult_words = (
        base_words
        .join(stats, Word.id == stats.c.word_id)
        .filter(difficulty > 0)
        .order_by(difficulty.desc())
        .limit(50)
        .all()
    )

    unseen_count = unseen_words.count()
    difficult_count = len(difficult_words)
    choose_unseen = (
        unseen_count > 0
        and (
            difficult_count == 0
            or random.randrange(unseen_count + difficult_count) < unseen_count
        )
    )

    if choose_unseen:
        word = unseen_words.order_by(func.random()).first()
        info_str.append('Это слово встретилось первый раз')
    elif difficult_words:
        word = random.choice(difficult_words)
        info_str.append(
            'Это слово встретилось из-за большого '
            'количества ошибок'
        )
    else:
        word = base_words.order_by(func.random()).first()
        info_str.append('Это слово встретилось случайно')

    if word:
        return render_template(
            'frame_inner.html',
            word=word,
            info_str=info_str,
            admin=admin,
            demo=demo,
        )
    else:
        return 'No words available', 404


# @bp.route('/get_word')
# def word():
#     word = Word.query.order_by(db.func.random()).first()
#     return jsonify({'html_word': word.get_html(),
#                     'explanation': word.explanation,
#                     'answers': word.get_answers(),
#                     'id': word.id})


@bp.route('/check_word', methods=['POST'])
@login_required
def check_word():
    user = current_user
    user_id = user.id

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'Invalid JSON'}), 400

    note_id = payload.get('id')
    answer = payload.get('answer')
    if not isinstance(note_id, int) or not isinstance(answer, str):
        return jsonify({'error': 'Invalid id or answer'}), 400

    is_paronym = len(answer) > 2 and answer.islower()
    if not is_paronym:
        note = db.session.get(Word, note_id)
        if note is None:
            return jsonify({'error': 'Word not found'}), 404
        if '_' in note.word:
            full_note = note.word.replace('_', note.answers[0])
        else:
            full_note = note.answers[0]
        explanation = note.explanation
        right_answer = note.answers[0]
    else:
        note = db.session.get(Sentence, note_id)
        if note is None:
            return jsonify({'error': 'Sentence not found'}), 404
        parse_word = MorphAnalyzer().parse(note.word.word)[0]
        inflected_word = parse_word.inflect(set(note.word_tags.split(',')))
        word_in_right_form = (
            inflected_word.word if inflected_word else parse_word.word
        )
        full_note = note.sentence.replace('_______', word_in_right_form)
        right_answer = word_in_right_form
        explanation = None

    if note and answer == right_answer:
        if user.settings.strike:
            session['strike'] = get_cached_strike(user_id) + 1

        if not is_paronym:
            add_action(user_id=user_id, word_id=note_id, action=Action.RIGHT_ANSWER)

        return jsonify({
            'correct': True, 'full_word': full_note, 'explanation': explanation,
            'strike': {
                'n': session.get('strike', None),
                'levels': current_app.config['STRIKE_LEVELS']
            }})
    else:
        if user.settings.strike:
            session['strike'] = 0

        if not is_paronym:
            add_action(user_id=user_id, word_id=note_id, action=Action.WRONG_ANSWER)

        return jsonify({
            'correct': False, 'full_word': full_note, 'explanation': explanation,
            'strike': {
                'n': session.get('strike'),
                'levels': current_app.config['STRIKE_LEVELS']
            }})


@bp.route('/mistake_report', methods=['POST'])
@login_required
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


@bp.route('/action/swipe_next', methods=['POST'])
@login_required
def action_swipe_next():
    user = current_user
    user_id = user.id

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'status': 'error', 'error': 'invalid JSON'}), 400
    try:
        word_id = int(payload.get('word_id'))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'error': 'invalid word id'}), 400

    if db.session.get(Word, word_id) is not None:
        last_words = (
            Action.query
            .filter(Action.user_id == user_id)
            .order_by(Action.datetime.desc())
            .limit(3)
        )
        last_ids = [e.word_id for e in last_words]
        if word_id in last_ids:
            return jsonify({
                'status': 'success',
                'strike': get_cached_strike(user_id),
            }), 200

        if user.settings.strike:
            session['strike'] = 0
        add_action(user_id=user_id, word_id=word_id, action=Action.SKIP)
        return jsonify({'status': 'success', 'strike': 0}), 200
    else:
        return jsonify({'status': 'error', 'error': 'word not found'}), 404
