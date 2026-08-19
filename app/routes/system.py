from flask import Blueprint, redirect, url_for


bp = Blueprint("system", __name__)


@bp.get("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="img/fav.ico"), code=308)
