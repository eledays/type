from typing import Any, cast

from flask import jsonify, request, url_for
from flask_login import current_user, login_required

from app.models import User
from app.routes.practice import api_bp
from app.services.practice import PracticeError, can_swipe, check_answer, report_word, skip_word


def error_response(error: PracticeError):
    payload: dict[str, Any] = {"error": error.code, "message": error.message}
    if error.code == "anonymous_limit_reached":
        payload["login_url"] = url_for(
            "auth.login", next=request.referrer or "/"
        )
    return jsonify(payload), error.status


@api_bp.post("/attempts")
@login_required
def create_attempt():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_json", "message": "Invalid JSON"}), 400
    note_id = payload.get("word_id", payload.get("id"))
    answer = payload.get("answer")
    if not isinstance(note_id, int) or not isinstance(answer, str):
        return jsonify({"error": "invalid_attempt", "message": "Invalid id or answer"}), 400
    try:
        result = check_answer(
            cast(User, current_user._get_current_object()), note_id, answer
        )
    except PracticeError as error:
        return error_response(error)
    return jsonify(result)


@api_bp.post("/attempts/skip")
@login_required
def skip_attempt():
    request_payload = request.get_json(silent=True)
    if not isinstance(request_payload, dict):
        return jsonify({
            "status": "error",
            "error": "invalid_json",
            "message": "Invalid JSON",
        }), 400
    word_id = request_payload.get("word_id")
    if not isinstance(word_id, int):
        return jsonify({
            "status": "error",
            "error": "invalid_word_id",
            "message": "Invalid word id",
        }), 400
    try:
        strike = skip_word(cast(User, current_user._get_current_object()), word_id)
    except PracticeError as error:
        payload: dict[str, Any] = {
            "status": "error",
            "error": error.code,
            "message": error.message,
        }
        if error.code == "anonymous_limit_reached":
            payload["login_url"] = url_for(
                "auth.login", next=request.referrer or "/"
            )
        return jsonify(payload), error.status
    return jsonify({"status": "success", "strike": strike})


@api_bp.get("/swipe-permission")
@login_required
def swipe_permission():
    word_id = request.args.get("word_id", type=int)
    if word_id is None:
        return jsonify({
            "status": "error",
            "error": "invalid_word_id",
            "message": "Invalid word id",
        }), 400
    allowed = can_swipe(cast(User, current_user._get_current_object()), word_id)
    return jsonify({"status": "yes" if allowed else "no"})


@api_bp.post("/words/<int:word_id>/reports")
@login_required
def create_word_report(word_id: int):
    if not report_word(word_id):
        return jsonify({"error": "word_not_found", "message": "Word not found"}), 404
    return jsonify({"status": "success"}), 201
