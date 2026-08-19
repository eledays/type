from flask import Blueprint


bp = Blueprint("practice", __name__)
api_bp = Blueprint("practice_api", __name__, url_prefix="/api/v1")

from app.routes.practice import api, pages  # noqa: E402, F401
