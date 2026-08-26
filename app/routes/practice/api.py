from typing import Any, cast

from flask import current_app, jsonify, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import limiter
from app.models import User
from app.routes.practice import api_bp
from app.services.practice import (
    PracticeError,
    check_answer,
    select_cards,
    serialize_cards,
    skip_card,
)
from app.services.reports import InvalidReport, create_error_report
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
        "cards": serialize_cards(cards, user.id, admin=admin)
    })
    response.headers["Cache-Control"] = "private, no-store"
    return response


@api_bp.post("/attempts")
@limiter.limit(
    lambda: current_app.config["RATE_LIMIT_MUTATION"],
    override_defaults=False,
)
@login_required
def create_attempt():
    """Проверяет и сохраняет попытку ответа на карточку.

    :return: JSON-ответ с результатом попытки или описанием ошибки.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_json", "message": "Invalid JSON"}), 400
    card_id = payload.get("card_id")
    answer = payload.get("answer")
    card_type = payload.get("card_type")
    if not isinstance(card_id, int) or not isinstance(answer, str):
        return jsonify({"error": "invalid_attempt", "message": "Invalid id or answer"}), 400
    if card_type not in {"spelling", "paronym"}:
        return jsonify({
            "error": "invalid_card_type",
            "message": "Invalid card type",
        }), 400
    try:
        user = cast(User, current_user._get_current_object())
        result = check_answer(user, card_id, answer, card_type)
    except PracticeError as error:
        return error_response(error)
    result["anonymous_remaining"] = get_anonymous_actions_remaining(user)
    return jsonify(result)


@api_bp.post("/attempts/skip")
@limiter.limit(
    lambda: current_app.config["RATE_LIMIT_MUTATION"],
    override_defaults=False,
)
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
    card_id = request_payload.get("card_id")
    if not isinstance(card_id, int):
        return jsonify({
            "status": "error",
            "error": "invalid_card_id",
            "message": "Invalid card id",
        }), 400
    card_type = request_payload.get("card_type")
    if card_type not in {"spelling", "paronym"}:
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
            card_id,
            card_type,
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


@api_bp.post("/reports")
@limiter.limit(
    lambda: current_app.config["RATE_LIMIT_REPORT"],
    override_defaults=False,
)
@login_required
def create_report():
    """Создаёт сообщение об общей ошибке или ошибке в упражнении."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_json", "message": "Invalid JSON"}), 400
    message = payload.get("message")
    item_id = payload.get("practice_item_id")
    if not isinstance(message, str):
        return jsonify({
            "error": "invalid_message",
            "message": "Message must be a string",
        }), 400
    if item_id is not None and type(item_id) is not int:
        return jsonify({
            "error": "invalid_practice_item_id",
            "message": "Practice item id must be an integer or null",
        }), 400
    try:
        user = cast(User, current_user._get_current_object())
        report = create_error_report(user, message, item_id)
    except InvalidReport as error:
        return jsonify({
            "error": error.code,
            "message": error.message,
        }), error.status
    return jsonify({"status": "success", "id": report.id}), 201
