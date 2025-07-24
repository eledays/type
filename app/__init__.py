from flask import Flask, render_template
app = Flask(__name__)

from dotenv import load_dotenv
load_dotenv('.env')

import os
ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "false").lower() == "true"

from config import Config
app.config.from_object(Config)

from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

from flask_migrate import Migrate
migrate = Migrate(app, db)

if ENABLE_TELEGRAM:
    import telebot
    bot = telebot.TeleBot(os.getenv('BOT_TOKEN'), parse_mode='html')

    from apscheduler.schedulers.background import BackgroundScheduler
    from app.utils import scheduler_run
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduler_run, trigger="interval", minutes=app.config.get('SEND_NOTIFICATION_PERIOD'))
    scheduler.start()

from app import models, utils
from app.routes import admin, core, filters, user_pages, users
from app.paronym import models as models_par
if ENABLE_TELEGRAM:
    from app import tg_handlers