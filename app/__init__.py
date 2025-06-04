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
import telebot
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))

from apscheduler.schedulers.background import BackgroundScheduler
from app.utils import scheduler_run
scheduler = BackgroundScheduler()
scheduler.add_job(scheduler_run, trigger="interval", minutes=app.config.get('SEND_NOTIFICATION_PERIOD'))
scheduler.start()

from app import routes, models, tg_handlers, utils