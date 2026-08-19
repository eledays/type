from app.extensions import db
from app.models import Word


def update_explanation(word_id: int, explanation: str) -> bool:
    word = db.session.get(Word, word_id)
    if word is None:
        return False
    word.explanation = explanation
    db.session.commit()
    return True


def delete_answer(word_id: int, answer: str) -> bool:
    word = db.session.get(Word, word_id)
    if word is None or answer not in word.answers:
        return False
    answers = word.answers[:]
    answers.remove(answer)
    word.answers = answers
    db.session.commit()
    return True
