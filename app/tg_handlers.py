from app import app, db, bot
from app.models import Action
from app.utils import send_day_summary

from telebot import types
import telebot


@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('Давай', web_app=types.WebAppInfo(url=app.config.get('URL')))
    markup.add(button)
    bot.send_message(message.chat.id, "Привет! Давай учить русский", reply_markup=markup)


@bot.message_handler(commands=['day'])
def day_results_handler(message):
    send_day_summary(message.chat.id)