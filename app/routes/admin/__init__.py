from flask import Blueprint


bp = Blueprint("admin_api", __name__, url_prefix="/api/v1/admin")
pages_bp = Blueprint("admin", __name__, url_prefix="/admin")

from app.routes.admin import api  # noqa: E402, F401
from app.routes.admin import pages  # noqa: E402, F401
