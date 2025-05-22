from flask import Flask, render_template
app = Flask(__name__)

from config import Config
app.config.from_object(Config)

from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

# from flask_login import LoginManager
# login = LoginManager(app)
# login.login_view = 'login'
login = None

from flask_migrate import Migrate
migrate = Migrate(app, db)

from dotenv import load_dotenv
load_dotenv('.env')

from app import routes, models, forms