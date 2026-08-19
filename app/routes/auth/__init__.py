from flask import Blueprint


bp = Blueprint("auth", __name__, url_prefix="/auth")

from app.routes.auth import views  # noqa: E402, F401
