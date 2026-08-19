"""Temporary compatibility aliases for clients using the pre-refactor URLs."""

from flask import Blueprint, jsonify, redirect, request, url_for
from flask_login import login_required

from app.routes.admin.api import patch_explanation, remove_answer
from app.routes.practice.api import create_attempt, skip_attempt, swipe_permission
from app.routes.profile.api import background, patch_settings
from app.security.decorators import admin_required
from app.services.practice import report_word


bp = Blueprint("legacy", __name__)


@bp.get("/task/<int:task_id>")
def task(task_id: int):
    return redirect(url_for("practice.index", task=task_id), code=308)


@bp.get("/category/<int:category_id>")
def category(category_id: int):
    return redirect(url_for("practice.index", category=category_id), code=308)


@bp.get("/mistakes")
def mistakes():
    return redirect(url_for("practice.index", mode="mistakes"), code=308)


@bp.get("/demo")
def demo():
    return redirect(url_for("practice.index"), code=308)


@bp.get("/get_frame")
def get_frame():
    return redirect(
        url_for(
            "practice.next_card",
            task=request.args.get("task_id"),
            category=request.args.get("category_id"),
            mode="mistakes" if request.args.get("mistakes") else None,
        ),
        code=308,
    )


@bp.get("/get_background")
@login_required
def get_background():
    return background()


@bp.get("/can_swipe")
def can_swipe_alias():
    return swipe_permission()


@bp.post("/check_word")
def check_word_alias():
    return create_attempt()


@bp.post("/action/swipe_next")
def swipe_next_alias():
    return skip_attempt()


@bp.post("/set_settings")
def settings_alias():
    return patch_settings()


@bp.post("/mistake_report")
@login_required
def mistake_report_alias():
    payload = request.get_json(silent=True)
    word_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(word_id, int):
        return jsonify({"error": "invalid_word_id"}), 400
    if not report_word(word_id):
        return jsonify({"error": "word_not_found"}), 404
    return jsonify({"status": "success"})


@bp.post("/add_explanation")
@admin_required
def add_explanation_alias():
    payload = request.get_json(silent=True)
    word_id = payload.get("word_id") if isinstance(payload, dict) else None
    if not isinstance(word_id, int):
        return jsonify({"error": "invalid_word_id"}), 400
    return patch_explanation(word_id)


@bp.post("/delete_answer")
@admin_required
def delete_answer_alias():
    payload = request.get_json(silent=True)
    word_id = payload.get("word_id") if isinstance(payload, dict) else None
    if not isinstance(word_id, int):
        return jsonify({"error": "invalid_word_id"}), 400
    return remove_answer(word_id)
