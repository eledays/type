from flask import Blueprint


bp = Blueprint("legal", __name__, url_prefix="/legal")

from app.routes.legal import pages  # noqa: E402, F401
