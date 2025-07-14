from flask import Flask, render_template
app = Flask(__name__)

from dotenv import load_dotenv
load_dotenv('.env')

from config import Config
app.config.from_object(Config)

from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

from flask_migrate import Migrate
migrate = Migrate(app, db)

from app import routes, models, utils
from app.paronym import models as models_par
