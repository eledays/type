from flask import Blueprint


bp = Blueprint("profile", __name__)
api_bp = Blueprint("profile_api", __name__, url_prefix="/api/v1/profile")

from app.routes.profile import api, pages  # noqa: E402, F401
