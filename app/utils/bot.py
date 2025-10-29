from app import app
from app.models import Action, Settings

if app.config.get("ENABLE_TELEGRAM", False):
    from app import bot
else:
    bot = None

from telebot import types

from datetime import datetime, timedelta
from sqlalchemy import or_, and_
from time import sleep
import os


def check_notifications():
    with app.app_context():
        start = datetime.now()
        end = start + timedelta(minutes=app.config.get("SEND_NOTIFICATION_PERIOD", 1))

        start = start.time()
        end = end.time()

        if start < end:
            users_to_notify = Settings.query.filter(
                Settings.notification == True,
                Settings.notification_time >= start,
                Settings.notification_time < end,
            ).all()
            users_to_notify_day_results = Settings.query.filter(
                Settings.day_results == True,
                Settings.day_results_time >= start,
                Settings.day_results_time < end,
            ).all()
        else:
            users_to_notify = Settings.query.filter(
                Settings.notification == True,
                or_(
                    Settings.notification_time >= start,
                    Settings.notification_time < end,
                ),
            ).all()
            users_to_notify_day_results = Settings.query.filter(
                Settings.day_results == True,
                or_(
                    Settings.day_results_time >= start, Settings.day_results_time < end
                ),
            ).all()

        # today_start = datetime.combine(datetime.now().date(), time(0, 0))
        # active_user_ids = db.session.query(Action.user_id).filter(
        #     Action.datetime >= today_start
        # ).distinct().all()
        # active_user_ids = {uid for uid, in active_user_ids}

        for user in users_to_notify:
            # if user.user_id in active_user_ids:
            #     continue

            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(
                "Поехали", web_app=types.WebAppInfo(url=app.config.get("URL"))
            )
            markup.add(button)

            if bot is not None:
                bot.send_message(
                    user.user_id, "Привет! Пора русский порешать", reply_markup=markup
                )
        for user in users_to_notify_day_results:
            send_day_summary(user.user_id)


def send_day_summary(user_id: int):
    with app.app_context():
        # Определяем временной диапазон "сегодня"
        now = datetime.now()
        today_end = datetime(
            now.year, now.month, now.day, now.hour, now.minute, now.second
        )
        today_start = today_end - timedelta(days=1)

        # Получаем все действия пользователя за день
        actions = Action.query.filter(
            and_(
                Action.user_id == user_id,
                Action.datetime >= today_start,
                Action.datetime < today_end,
            )
        ).all()

        # Подсчёт по категориям действий
        right = sum(a.action == Action.RIGHT_ANSWER for a in actions)
        wrong = sum(a.action == Action.WRONG_ANSWER for a in actions)
        skipped = sum(a.action == Action.SKIP for a in actions)

        total = right + wrong + skipped

        if total == 0:
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(
                "Решать", web_app=types.WebAppInfo(url=app.config.get("URL"))
            )
            markup.add(button)
            try:
                if bot is not None:
                    bot.send_message(
                        user_id,
                        "<b>Итоги дня</b>\n\nКажется, сегодня ничего нет. Давай решим хотя бы пару заданий?",
                        reply_markup=markup,
                    )
            except:
                pass

        text = (
            f"<b>Итоги дня</b>\n\n"
            f"- Правильных ответов: <b>{right}</b>\n"
            f"- Ошибок: <b>{wrong}</b>\n"
            f"- Пропущено: <b>{skipped}</b>\n"
            f"- Всего заданий сегодня: <b>{total}</b>"
        )

        if right > 100:
            text += "\n\nОтличный результат! Продолжай в том же духе!"

        if bot is not None:
            bot.send_message(user_id, text)


def send_all_message(text):
    success, fail = 0, 0
    with app.app_context():
        users = Settings.query.all()
        for user in users:
            try:
                if bot is not None:
                    bot.send_message(user.user_id, text)
                    success += 1
            except:
                fail += 1
            sleep(0.5)

    if bot is not None:
        bot.send_message(
        os.getenv("ADMIN_ID", 0), f"Отправлено\nУспешно: {success}\nОшибки: {fail}"
    )
