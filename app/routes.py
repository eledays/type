from app import app, db, login
from app.forms import LoginForm, RegistrationForm
from app.models import Word
from app.utils import verify_telegram_auth

from flask import render_template, redirect, url_for, jsonify, request, send_file

from time import sleep
import json
import datetime
import os
import random
# from flask_login import login_required, current_user, login_user, logout_user
# from werkzeug.security import generate_password_hash, check_password_hash


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/settings')
def settings():
    with open(app.static_folder + '/css/themes/themes.json', 'r', encoding='utf-8') as file:
        themes = file.read()
    themes = json.loads(themes)
    return render_template('settings.html', themes=themes)


@app.route('/get_frame')
def get_frame():
    return render_template('frame_inner.html')


@app.route('/get_word')
def word():
    word = Word.query.order_by(db.func.random()).first()
    return jsonify({'html_word': word.get_html(),
                    'explanation': word.explanation,
                    'answers': word.get_answers(),
                    'id': word.id,
                    'right_answer': word.answers[0],
                    'full_word': word.word.replace('_', word.answers[0])})
    

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
    filename = random.choice(os.listdir('app/static/img/backs'))
    response = send_file(f'static/img/backs/{filename}')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/verify-hash', methods=['POST'])
def verify_hash():
    data = request.get_json()
    init_data = data.get('initData', '')

    if verify_telegram_auth(init_data, os.getenv('BOT_TOKEN')):
        return jsonify({'valid': True})
    else:
        return jsonify({'valid': False})


@app.after_request
def add_cache_control_headers(response):
    if request.path.endswith('.css') or request.path.endswith('.js'):
        response.headers['Cache-Control'] = 'public, max-age=31536000'
    return response