from flask import current_app, jsonify, request

from app.extensions import limiter
from app.routes.admin import bp
from app.security.decorators import admin_required
from app.services.admin import delete_answer, update_explanation


@bp.patch("/words/<int:word_id>/explanation")
@limiter.limit(
    lambda: current_app.config["RATE_LIMIT_MUTATION"],
    override_defaults=False,
)
@admin_required
def patch_explanation(word_id: int):
    """Обновляет объяснение слова от имени администратора.

    :param word_id: Идентификатор слова из адреса запроса.
    :return: JSON-ответ о результате обновления.
    """
    payload = request.get_json(silent=True)
    explanation = payload.get("explanation") if isinstance(payload, dict) else None
    if not isinstance(explanation, str):
        return jsonify({
            "error": "invalid_explanation",
            "message": "Explanation must be a string",
        }), 400
    if not update_explanation(word_id, explanation):
        return jsonify({
            "error": "word_not_found",
            "message": "Word not found",
        }), 404
    return jsonify({"status": "success"})


@bp.delete("/words/<int:word_id>/answers")
@limiter.limit(
    lambda: current_app.config["RATE_LIMIT_MUTATION"],
    override_defaults=False,
)
@admin_required
def remove_answer(word_id: int):
    """Удаляет вариант ответа от имени администратора.

    :param word_id: Идентификатор слова из адреса запроса.
    :return: JSON-ответ о результате удаления.
    """
    payload = request.get_json(silent=True)
    answer = payload.get("answer") if isinstance(payload, dict) else None
    if not isinstance(answer, str):
        return jsonify({
            "error": "invalid_answer",
            "message": "Answer must be a string",
        }), 400
    if not delete_answer(word_id, answer):
        return jsonify({
            "error": "word_or_answer_not_found",
            "message": "Word or answer not found",
        }), 404
    return jsonify({"status": "success"})
