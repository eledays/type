"""Навигационные перенаправления со старых пользовательских URL."""

from flask import Blueprint, redirect, url_for


bp = Blueprint("legacy", __name__)


@bp.get("/task/<int:task_id>")
def task(task_id: int):
    """Перенаправляет старый адрес задания на каноническую ленту.

    :param task_id: Идентификатор задания.
    :return: Постоянное перенаправление.
    """
    return redirect(url_for("practice.index", task=task_id), code=308)


@bp.get("/category/<int:category_id>")
def category(category_id: int):
    """Перенаправляет старый адрес категории на каноническую ленту.

    :param category_id: Идентификатор категории.
    :return: Постоянное перенаправление.
    """
    return redirect(url_for("practice.index", category=category_id), code=308)


@bp.get("/mistakes")
def mistakes():
    """Перенаправляет старый адрес ошибок в режим проблемных слов.

    :return: Постоянное перенаправление.
    """
    return redirect(url_for("practice.index", mode="mistakes"), code=308)


@bp.get("/demo")
def demo():
    """Перенаправляет старый демонстрационный адрес на главную ленту.

    :return: Постоянное перенаправление.
    """
    return redirect(url_for("practice.index"), code=308)
