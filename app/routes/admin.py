from app import app, db
from app.models import Word

from flask import render_template, request, session

import os


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