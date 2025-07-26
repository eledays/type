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

from apscheduler.schedulers.background import BackgroundScheduler
from app.utils import check_notifications, do_backup

backup_scheduler = BackgroundScheduler(persist_jobs=False)
backup_scheduler.add_job(do_backup, trigger="interval", days=app.config.get('BACKUP_PERIOD'))
backup_scheduler.start()

if ENABLE_TELEGRAM:
    import telebot
    bot = telebot.TeleBot(os.getenv('BOT_TOKEN'), parse_mode='html')

    notification_scheduler = BackgroundScheduler(persist_jobs=False)
    notification_scheduler.add_job(check_notifications, trigger="interval", minutes=app.config.get('SEND_NOTIFICATION_PERIOD'))
    notification_scheduler.start()

from app import models, utils
from app.routes import admin, core, filters, user_pages, users
from app.paronym import models as models_par
if ENABLE_TELEGRAM:
    from app import tg_handlers