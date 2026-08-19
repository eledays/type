from app.extensions import db
from app.models import SpellingExercise


def update_explanation(word_id: int, explanation: str) -> bool:
    """Обновляет административное объяснение слова.

    :param word_id: Идентификатор слова.
    :param explanation: Новый текст объяснения.
    :return: ``True`` при успешном обновлении, иначе ``False``.
    """
    word = db.session.get(SpellingExercise, word_id)
    if word is None:
        return False
    word.explanation = explanation
    db.session.commit()
    return True


def delete_answer(word_id: int, answer: str) -> bool:
    """Удаляет вариант ответа у слова.

    :param word_id: Идентификатор слова.
    :param answer: Удаляемый вариант ответа.
    :return: ``True`` при успешном удалении, иначе ``False``.
    """
    word = db.session.get(SpellingExercise, word_id)
    if (
        word is None
        or answer not in word.answers
        or answer == word.correct_answer
    ):
        return False
    answers = word.answers[:]
    answers.remove(answer)
    word.answers = answers
    db.session.commit()
    return True
