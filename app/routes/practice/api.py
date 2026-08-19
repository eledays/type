from typing import Any, cast

from flask import current_app, jsonify, request, session, url_for
from flask_login import current_user, login_required

from app.models import User
from app.routes.practice import api_bp
from app.services.practice import (
    PracticeError,
    check_answer,
    report_word,
    select_cards,
    serialize_card,
    skip_card,
)
from app.utils import get_anonymous_actions_remaining


def error_response(error: PracticeError):
    """Преобразует доменную ошибку практики в JSON-ответ.

    :param error: Ошибка сервисного слоя.
    :return: Flask-ответ с телом ошибки и соответствующим статусом.
    """
    payload: dict[str, Any] = {"error": error.code, "message": error.message}
    if error.code == "anonymous_limit_reached":
        payload["login_url"] = url_for(
            "auth.login", next=request.referrer or "/"
        )
    return jsonify(payload), error.status


@api_bp.get("/practice/cards")
@login_required
def get_cards():
    """Возвращает пакет персональных карточек для клиентского пула.

    :return: JSON-ответ со списком карточек или описанием ошибки.
    """
    raw_count = request.args.get("limit")
    try:
        count = (
            int(raw_count)
            if raw_count is not None
            else int(current_app.config["PRACTICE_CARD_BATCH_SIZE"])
        )
    except ValueError:
        return jsonify({
            "error": "invalid_limit",
            "message": "Limit must be an integer",
        }), 400

    excluded: set[int] = set()
    raw_excluded = request.args.get("exclude", "")
    if raw_excluded:
        try:
            excluded = {
                int(value) for value in raw_excluded.split(",") if value
            }
        except ValueError:
            return jsonify({
                "error": "invalid_exclude",
                "message": "Exclude must contain comma-separated ids",
            }), 400

    try:
        user = cast(User, current_user._get_current_object())
        admin = (
            user.is_admin
            and bool(session.get("admin", False))
            and request.args.get("admin") == "1"
        )
        cards = select_cards(
            user,
            count,
            task_id=request.args.get("task", ""),
            category_id=request.args.get("category", ""),
            mistakes=request.args.get("mode") == "mistakes",
            exclude_ids=excluded,
        )
    except PracticeError as error:
        return error_response(error)
    response = jsonify({
        "cards": [serialize_card(card, admin=admin) for card in cards]
    })
    response.headers["Cache-Control"] = "private, no-store"
    return response


@api_bp.post("/attempts")
@login_required
def create_attempt():
    """Проверяет и сохраняет попытку ответа на карточку.

    :return: JSON-ответ с результатом попытки или описанием ошибки.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_json", "message": "Invalid JSON"}), 400
    note_id = payload.get("card_id")
    answer = payload.get("answer")
    note_type = payload.get("card_type")
    if not isinstance(note_id, int) or not isinstance(answer, str):
        return jsonify({"error": "invalid_attempt", "message": "Invalid id or answer"}), 400
    if note_type not in {"word", "sentence"}:
        return jsonify({
            "error": "invalid_card_type",
            "message": "Invalid card type",
        }), 400
    try:
        user = cast(User, current_user._get_current_object())
        result = check_answer(user, note_id, answer, note_type)
    except PracticeError as error:
        return error_response(error)
    result["anonymous_remaining"] = get_anonymous_actions_remaining(user)
    return jsonify(result)


@api_bp.post("/attempts/skip")
@login_required
def skip_attempt():
    """Пропускает карточку с серверной проверкой серии и квоты.

    :return: JSON-ответ с новой серией либо запросом подтверждения.
    """
    request_payload = request.get_json(silent=True)
    if not isinstance(request_payload, dict):
        return jsonify({
            "status": "error",
            "error": "invalid_json",
            "message": "Invalid JSON",
        }), 400
    note_id = request_payload.get("card_id")
    if not isinstance(note_id, int):
        return jsonify({
            "status": "error",
            "error": "invalid_card_id",
            "message": "Invalid card id",
        }), 400
    note_type = request_payload.get("card_type")
    if note_type not in {"word", "sentence"}:
        return jsonify({
            "status": "error",
            "error": "invalid_card_type",
            "message": "Invalid card type",
        }), 400
    confirmed = request_payload.get("confirmed", False)
    if not isinstance(confirmed, bool):
        return jsonify({
            "status": "error",
            "error": "invalid_confirmation",
            "message": "Confirmed must be a boolean",
        }), 400
    try:
        user = cast(User, current_user._get_current_object())
        strike = skip_card(
            user,
            note_id,
            note_type,
            confirmed=confirmed,
        )
    except PracticeError as error:
        payload: dict[str, Any] = {
            "status": (
                "confirmation_required"
                if error.code == "strike_reset_confirmation_required"
                else "error"
            ),
            "error": error.code,
            "message": error.message,
        }
        if error.code == "anonymous_limit_reached":
            payload["login_url"] = url_for(
                "auth.login", next=request.referrer or "/"
            )
        return jsonify(payload), error.status
    return jsonify({
        "status": "success",
        "strike": strike,
        "anonymous_remaining": get_anonymous_actions_remaining(user),
    })


@api_bp.post("/words/<int:word_id>/reports")
@login_required
def create_word_report(word_id: int):
    """Создаёт пользовательский отчёт об ошибке в слове.

    :param word_id: Идентификатор слова из адреса запроса.
    :return: JSON-ответ о создании отчёта или отсутствии слова.
    """
    if not report_word(word_id):
        return jsonify({"error": "word_not_found", "message": "Word not found"}), 404
    return jsonify({"status": "success"}), 201
