from app.auth import admin_required
from app.extensions import db
from app.models import Word

from flask import Blueprint, request


bp = Blueprint("admin", __name__)


@bp.route('/add_explanation', methods=['POST'])
@admin_required
def add_explanation():
    payload = request.get_json(silent=True) or {}
    word_id = payload.get('word_id')
    explanation = payload.get('explanation')
    word = db.session.get(Word, word_id) if isinstance(word_id, int) else None

    if word is not None and isinstance(explanation, str):
        word.explanation = explanation
        db.session.commit()
        return 'ok', 200
    return 'Error', 400


@bp.route('/delete_answer', methods=['POST'])
@admin_required
def delete_answer():
    payload = request.get_json(silent=True) or {}
    word_id = payload.get('word_id')
    answer = payload.get('answer')
    word = db.session.get(Word, word_id) if isinstance(word_id, int) else None

    if word is not None and answer in word.answers:
        answers = word.answers[:]
        answers.remove(answer)
        word.answers = answers
        db.session.commit()
        return 'ok', 200
    return 'Error', 400
