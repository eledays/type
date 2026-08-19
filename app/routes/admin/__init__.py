from flask import Blueprint


bp = Blueprint("admin_api", __name__, url_prefix="/api/v1/admin")

from app.routes.admin import api  # noqa: E402, F401
