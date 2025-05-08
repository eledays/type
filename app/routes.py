from app import app, db, login
from app.forms import LoginForm, RegistrationForm
from app.models import Word

from flask import render_template, redirect, url_for, jsonify, request

from time import sleep
import json
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
    print(word.get_html())
    return jsonify({'html_word': word.get_html(),
                    'explanation': word.explanation,
                    'answers': word.get_answers(),
                    'id': word.id})


@app.route('/check_word', methods=['POST'])
def check_word():
    word_id = request.json.get('id')
    answer = request.json.get('answer')
    word = Word.query.get(word_id)
    if word and answer == word.answers[0]:
        full_word = word.word.replace('_', word.answers[0])
        return jsonify({'correct': True, 'full_word': full_word})
    else:
        return jsonify({'correct': False})
    

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if current_user.is_authenticated:
#         return redirect(url_for('index'))
#     form = LoginForm()

#     if form.validate():
#         user = User.query.filter_by(username=form.username.data).first()
#         if user and check_password_hash(user.password_hash, form.password.data):
#             login_user(user)
#             return redirect(url_for('index'))
#         else:
#             form.username.errors.append('Неверное имя пользователя или пароль')

#     return render_template('login.html', form=form)


# @app.route('/logout')
# def logout():
#     logout_user()
#     return redirect(url_for('index'))


# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     form = RegistrationForm()
#     if form.validate():
#         user = User()
#         user.username = form.username.data
#         user.password_hash = generate_password_hash(form.password.data)
#         db.session.add(user)
#         db.session.commit()
#         login_user(user)
#         return redirect(url_for('index'))
#     return render_template('register.html', form=form)