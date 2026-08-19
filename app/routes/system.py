from flask import Blueprint, redirect, url_for


bp = Blueprint("system", __name__)


@bp.get("/favicon.ico")
def favicon():
    """Перенаправляет стандартный адрес favicon на статический файл.

    :return: Перенаправление к иконке приложения.
    """
    return redirect(url_for("static", filename="img/fav.ico"), code=308)
