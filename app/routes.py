from app import app, db, login
from app.forms import LoginForm, RegistrationForm
from app.models import Word, Action, Category
from app.utils import add_action

from flask import render_template, redirect, url_for, jsonify, request, send_file, session
from init_data_py import InitData

from time import sleep
import json
import datetime
import os
import random


@app.route('/')
def index():
    return render_template('index.html', strike=session.get('strike', 0))


@app.route('/task/<int:task_id>')
def task(task_id):
    return render_template('index.html', strike=session.get('strike', 0), params=f'task_id={task_id}')


@app.route('/category/<int:category_id>')
def category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return 'Category not found', 404    
    return render_template('index.html', strike=session.get('strike', 0), params=f'category_id={category_id}')


@app.route('/settings')
def settings():
    categories = Category.query.all()
    return render_template('settings.html', categories=categories, tasks=app.config['TASKS'])


@app.route('/get_frame')
def get_frame():
    task_id = request.args.get('task_id', '')
    category_id = request.args.get('category_id', '')
    category = Category.query.get(category_id)

    if task_id:
        words = Word.query.filter(Word.task_number == task_id)
        info_str=f'Задание №{task_id}'
    elif category_id:
        words = Word.query.filter(Word.category_id == category_id)
        info_str=f'Категория "{category.name}"'
    else:
        words = Word.query
        info_str = ''

    word = words.order_by(db.func.random()).first()
    if word:
        return render_template('frame_inner.html', word=word, info_str=info_str)   
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
    
    word_id = request.json.get('id')
    answer = request.json.get('answer')
    word = Word.query.get(word_id)
    full_word = word.word.replace('_', word.answers[0])
    if word and answer == word.answers[0]:
        session['strike'] = session.get('strike', 0) + 1
        add_action(user_id=session['user_id'], word_id=word_id, action=Action.RIGHT_ANSWER)
        return jsonify({
            'correct': True, 'full_word': full_word, 
            'strike': {
                'n': session['strike'],
                'levels': app.config['STRIKE_LEVELS']
            }})
    else:
        session['strike'] = 0
        add_action(user_id=session['user_id'], word_id=word_id, action=Action.WRONG_ANSWER)
        return jsonify({
            'correct': False, 'full_word': full_word, 
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
    if 'strike' not in session:
        session['strike'] = 0
    
    levels = app.config['STRIKE_LEVELS']

    if session['strike'] < levels[0]:
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


@app.route('/verify_hash', methods=['POST'])
def verify_hash():
    data = request.get_json()
    init_data = InitData.parse(data.get('initData', ''))

    if init_data.validate(os.getenv('BOT_TOKEN')):
        session['user_id'] = init_data.user.id
        return jsonify({'valid': True})
    else:
        session['user_id'] = None
        return jsonify({'valid': False})
    

@app.route('/set_user_id', methods=['POST'])
def set_user_id():
    user_id = request.json.get('user_id')
    if user_id is not None and user_id.startswith('unsafe_'):
        session['user_id'] = user_id
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error'}), 400
    

@app.route('/action/swipe_next', methods=['POST'])
def action_swipe_next():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401
    
    word_id = request.json.get('word_id')
    if word_id is not None:
        add_action(user_id=session['user_id'], word_id=word_id, action=Action.SAVE_WORD)

    add_action(user_id=session['user_id'], word_id=word_id, action=Action.SKIP)
    return jsonify({'status': 'success'})


# @app.after_request
# def add_cache_control_headers(response):
#     if request.path.endswith('.css') or request.path.endswith('.js'):
#         response.headers['Cache-Control'] = 'public, max-age=31536000'
#     return response