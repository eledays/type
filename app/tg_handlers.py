from app import app, db, bot
from app.models import Action
from app.utils import send_day_summary, send_all_message

from telebot import types
import telebot

import os


@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('Давай', web_app=types.WebAppInfo(url=app.config.get('URL')))
    markup.add(button)
    bot.send_message(message.chat.id, "Привет! Давай учить русский", reply_markup=markup)


@bot.message_handler(commands=['day'])
def day_results_handler(message):
    send_day_summary(message.chat.id)


@bot.message_handler(commands=['all_message'])
def all_message(message, step=0, data=None):
    if data is None:
        data = {}

    if message.chat.id != int(os.getenv('ADMIN_ID')):
        return 
    
    if step == 0:
        message = bot.send_message(message.chat.id, 'Отправь текст сообщения')
        bot.register_next_step_handler(message, all_message, 1)
    elif step == 1:
        data['text'] = message.text
        bot.send_message(message.chat.id, data['text'])
        message = bot.send_message(message.chat.id, 'Пришли "Отправить", чтобы отправить всем пользователям')
        bot.register_next_step_handler(message, all_message, 2, data)
    elif step == 2:
        if message.text == 'Отправить':
            send_all_message(data['text'])
        else:
            bot.send_message(message.chat.id, 'Отменено')