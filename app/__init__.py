from flask import Flask
from flask_login import LoginManager
app = Flask(__name__)

from config import settings
app.config.from_mapping(settings.to_flask_config())

from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

from flask_migrate import Migrate
migrate = Migrate(app, db, compare_type=True, render_as_batch=True)

login_manager = LoginManager(app)

bot = None

from app import models


@login_manager.user_loader
def load_user(user_id: str) -> models.User | None:
    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(models.User, parsed_user_id)


from app.routes import admin, core, filters, user_pages, users
