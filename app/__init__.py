from dotenv import load_dotenv
load_dotenv('.env')

from flask import Flask, render_template
app = Flask(__name__)

from config import Config
app.config.from_object(Config)

from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

from flask_migrate import Migrate
migrate = Migrate(app, db)

bot = None

from app import models, utils
from app.routes import admin, core, filters, user_pages, users
from app.paronym import models as models_par
