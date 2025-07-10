import pymorphy3.analyzer

from app import app, db
from app.models import Word, Action, Category, Settings
from app.paronym.models import Paronym, Sentence
from app.utils import add_action, get_strike, get_user_stats

from flask import render_template, redirect, url_for, jsonify, request, send_file, session
from init_data_py import InitData
from sqlalchemy import and_, func, case
import telebot
from pymorphy3.analyzer import MorphAnalyzer

from time import sleep
import json
import datetime
import os
import random
import ast


@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template('auth.html')
    
    user_id = session.get('user_id')
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()

    if user_settings is None:
        user_settings = Settings(user_id=user_id)
        db.session.add(user_settings)
        db.session.commit()

    strike = session.get('strike', get_strike(user_id)) if user_settings.strike else None

    return render_template('index.html', strike=strike)


@app.route('/task/<int:task_id>')
def task(task_id):
    return render_template('index.html', strike=session.get('strike', get_strike(session.get('user_id'))), params=f'task_id={task_id}')


@app.route('/category/<int:category_id>')
def category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return 'Category not found', 404    
    return render_template('index.html', strike=session.get('strike', get_strike(session.get('user_id'))), params=f'category_id={category_id}')


@app.route('/mistakes')
def mistakes():
    if 'user_id' not in session:
        return 'Not authenticated', 401
    
    return render_template('index.html', strike=session.get('strike', 0, get_strike(session.get('user_id'))), params=f'mistakes=true')


@app.route('/filters')
def filters():
    categories = Category.query.all()
    return render_template('filters.html', categories=categories, tasks=app.config['TASKS'])


@app.route('/get_frame')
def get_frame():
    task_id = request.args.get('task_id', '')
    category_id = request.args.get('category_id', '')
    category = Category.query.get(category_id)
    mistakes = request.args.get('mistakes', '') 
    admin = session.get('admin', False) 

    user_id = session.get('user_id')
    admin = (str(user_id) == str(os.getenv('ADMIN_ID'))) and admin

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
        return render_template('frame_inner.html', word=word, info_str=info_str, admin=admin)
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
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401
    
    user_id = session.get('user_id')
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()

    note_id = request.json.get('id')
    answer = request.json.get('answer')
    is_paronym = len(answer) != 1
    if not is_paronym:
        note = Word.query.get(note_id)
        full_note = note.word.replace('_', note.answers[0])
        explanation = note.explanation
        right_answer = note.answers[0]
    else:
        note = Sentence.query.get(note_id)
        parse_word = MorphAnalyzer().parse(note.word.word)[0]
        word_in_right_form = parse_word.inflect(note.word_tags).word
        full_note = note.sentence.replace('_______', word_in_right_form)
        right_answer = word_in_right_form
        explanation = None

    if note and answer == right_answer:
        if user_settings.strike:
            session['strike'] = session.get('strike', get_strike(user_id)) + 1

        if not is_paronym:
            add_action(user_id=session['user_id'], word_id=note_id, action=Action.RIGHT_ANSWER)

        return jsonify({
            'correct': True, 'full_word': full_note, 'explanation': explanation,
            'strike': {
                'n': session['strike'],
                'levels': app.config['STRIKE_LEVELS']
            }})
    else:
        if user_settings.strike:
            session['strike'] = 0

        if not is_paronym:
            add_action(user_id=session['user_id'], word_id=note_id, action=Action.WRONG_ANSWER)

        return jsonify({
            'correct': False, 'full_word': full_note, 'explanation': explanation,
            'strike': { 
                'n': session['strike'],
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


@app.route('/get_background')
def get_background():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401
    
    user_id = session.get('user_id')
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()

    if 'strike' not in session:
        session['strike'] = get_strike(user_id)
    
    levels = app.config['STRIKE_LEVELS']

    if str(user_id) in [str(os.getenv('SECURE_ID')), str(os.getenv('ADMIN_ID'))] and session['strike'] >= levels[0]:
        filename = random.choice(os.listdir(f'app/secure_static/backs/'))
        response = send_file(f'secure_static/backs/{filename}')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    elif session['strike'] < levels[0] or not user_settings.strike:
        path = 'dark'
    elif session['strike'] < levels[1]:
        path = 'yellow'
    else:
        path = 'dark'

    filename = random.choice(os.listdir(f'app/static/img/backs/{path}'))
    response = send_file(f'static/img/backs/{path}/{filename}')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
    

@app.route('/set_user_id', methods=['POST'])
def set_user_id():
    user_id = request.json.get('user_id')
    if user_id is not None:
        session['user_id'] = user_id
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error'}), 400
    

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


# @app.after_request
# def add_cache_control_headers(response):
#     if request.path.endswith('.css') or request.path.endswith('.js'):
#         response.headers['Cache-Control'] = 'public, max-age=31536000'
#     return response


@app.route('/favicon.ico')
def favicon():
    return send_file('static/img/fav.ico', mimetype='image/x-icon')


@app.route('/can_swipe', methods=['GET'])
def can_swipe():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401

    user_id = session.get('user_id')
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()
    word_id = request.args.get('word_id')

    if not user_settings.strike:
        return jsonify({'status': 'yes'}), 200

    if word_id is None:
        return jsonify({'status': 'error', 'message': 'No word id'}), 401
    
    word_id = int(word_id)
    last_words = Action.query.filter(Action.user_id == user_id).order_by(Action.datetime.desc()).limit(3)
    last_ids = [e.word_id for e in last_words]
    strike = session.get('strike', get_strike(user_id))

    if word_id in last_ids or strike <= 3:
        return jsonify({'status': 'yes'}), 200
    else:
        return jsonify({'status': 'no'}), 200


@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return render_template('auth.html')
    
    user_id = session.get('user_id')
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()

    if user_settings is None:
        user_settings = Settings(user_id=user_id)
        db.session.add(user_settings)
        db.session.commit()

    admin = str(user_id) == str(os.getenv('ADMIN_ID'))
    if admin and session.get('admin', False):
        admin = 2
    elif admin and not session.get('admin', False):
        admin = 1

    stats = get_user_stats(user_id)
    if admin:
        stats["explanations"] = Word.query.filter(Word.explanation.isnot(None)).count()
        stats["users"] = Settings.query.count()

    return render_template('settings.html', settings=user_settings, admin=admin, stats=stats)
    

@app.route('/set_settings', methods=['POST'])
def set_settings():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401
    
    user_id = session.get('user_id')
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()

    if 'admin' in request.json and str(user_id) == str(os.getenv('ADMIN_ID')):
        session['admin'] = request.json.get('admin')
        return 'ok', 200
    
    for k, v in request.json.items():
        if hasattr(user_settings, k):
            if k.endswith('_time'):
                v = datetime.datetime.strptime(v, '%H:%M').time()
            setattr(user_settings, k, v)
        else:
            db.session.rollback()
            return 'Unknown field', 400
    db.session.commit()

    return 'ok', 200


@app.route('/add_explanation', methods=['POST'])
def add_explanation():
    if 'user_id' not in session:
        return render_template('auth.html')
    
    user_id = session.get('user_id')

    if str(user_id) != str(os.getenv('ADMIN_ID')):
        return 'Access denied', 403

    word_id = request.json.get('word_id')
    explanation = request.json.get('explanation')

    print(word_id)

    word = Word.query.filter(Word.id == word_id).first()

    if word:
        word.explanation = explanation
        db.session.commit()
        return 'ok', 200
    return 'Error', 400


@app.route('/delete_answer', methods=['POST'])
def delete_answer():
    if 'user_id' not in session:
        return render_template('auth.html')
    
    user_id = session.get('user_id')

    if str(user_id) != str(os.getenv('ADMIN_ID')):
        return 'Access denied', 403

    word_id = request.json.get('word_id')
    answer = request.json.get('answer')

    word = Word.query.filter(Word.id == word_id).first()
    print(word_id, type(word.answers), answer in word.answers)
    if word:
        answers = word.answers[:]
        answers.remove(answer)
        word.answers = answers
        db.session.commit()
        print(word.answers)
        return 'ok', 200
    return 'Error', 400