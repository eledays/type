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

import os
bot = None

if app.config.get('ENABLE_TELEGRAM', False):
    import telebot
    bot = telebot.TeleBot(os.getenv('BOT_TOKEN'), parse_mode='html')

from apscheduler.schedulers.background import BackgroundScheduler
from app.utils import check_notifications, do_backup

do_backup()

backup_scheduler = BackgroundScheduler(persist_jobs=False)
backup_scheduler.add_job(do_backup, trigger="interval", days=app.config.get('BACKUP_PERIOD'))
backup_scheduler.start()

if app.config.get('ENABLE_TELEGRAM', False):
    notification_scheduler = BackgroundScheduler(persist_jobs=False)
    notification_scheduler.add_job(check_notifications, trigger="interval", minutes=app.config.get('SEND_NOTIFICATION_PERIOD'))
    notification_scheduler.start()

from app import models, utils
from app.routes import admin, core, filters, user_pages, users
from app.paronym import models as models_par
if app.config.get('ENABLE_TELEGRAM', False):
    from app import tg_handlers