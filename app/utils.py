from app import app, db, ENABLE_TELEGRAM
from app.models import Action, Settings, Word
if ENABLE_TELEGRAM:
    from app import bot

from telebot import types

from datetime import datetime, time, timedelta
from sqlalchemy import or_, and_, desc, func
from time import sleep
import os


def add_action(user_id, word_id, action):
    if user_id is None or action is None:
        return None
    action = Action(user_id=user_id, word_id=word_id, action=action)
    db.session.add(action)
    db.session.commit()


def scheduler_run():
    with app.app_context():
        start = datetime.now()
        end = start + timedelta(minutes=app.config.get('SEND_NOTIFICATION_PERIOD'))

        start = start.time()
        end = end.time()

        if start < end:
            users_to_notify = Settings.query.filter(
                Settings.notification == True,
                Settings.notification_time >= start,
                Settings.notification_time < end
            ).all()
            users_to_notify_day_results = Settings.query.filter(
                Settings.day_results == True,
                Settings.day_results_time >= start,
                Settings.day_results_time < end
            ).all()
        else:
            users_to_notify = Settings.query.filter(
                Settings.notification == True,
                or_(
                    Settings.notification_time >= start,
                    Settings.notification_time < end
                )
            ).all()
            users_to_notify_day_results = Settings.query.filter(
                Settings.day_results == True,
                or_(
                    Settings.day_results_time >= start,
                    Settings.day_results_time < end
                )
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
            button = types.InlineKeyboardButton('Поехали', web_app=types.WebAppInfo(url=app.config.get('URL')))
            markup.add(button)

            bot.send_message(user.user_id, 'Привет! Пора русский порешать', reply_markup=markup)
        for user in users_to_notify_day_results:
            send_day_summary(user.user_id)


def get_strike(user_id):
    with app.app_context():
        actions = Action.query.filter(
            Action.user_id == user_id,
            Action.action.in_([Action.RIGHT_ANSWER, Action.WRONG_ANSWER, Action.SKIP])
        ).order_by(desc(Action.datetime)).all()

        streak = 0
        for action in actions:
            if action.action == Action.RIGHT_ANSWER:
                streak += 1
            else:
                break

        return streak


def get_user_stats(user_id: int):
    with app.app_context():
        actions = Action.query.filter(
            Action.user_id == user_id,
            Action.action.in_([Action.RIGHT_ANSWER, Action.WRONG_ANSWER, Action.SKIP])
        ).order_by(Action.datetime).all()

        total_attempts = 0
        mistakes = 0
        skips = 0
        correct = 0
        best_streak = 0
        current_streak = 0

        total_time = timedelta()
        last_time = None
        max_pause = timedelta(minutes=10)

        for action in actions:
            total_attempts += 1

            if last_time is not None:
                pause = action.datetime - last_time
                if pause <= max_pause:
                    total_time += pause
            last_time = action.datetime

            if action.action == Action.RIGHT_ANSWER:
                correct += 1
                current_streak += 1
                best_streak = max(best_streak, current_streak)
            elif action.action == Action.WRONG_ANSWER:
                mistakes += 1
                current_streak = 0
            elif action.action == Action.SKIP:
                skips += 1
                current_streak = 0

        percent_correct = (correct / total_attempts * 100) if total_attempts else 0
        avg_time = (total_time / total_attempts) if total_attempts else timedelta()

        return {
            "correct": correct,
            "mistakes": mistakes,
            "skips": skips,
            "correct_percent": round(percent_correct, 1),
            "avg_time_per_word": round(avg_time.seconds, 1),
            "best_streak": best_streak
        }


def send_day_summary(user_id: int) -> str:
    with app.app_context():
        # Определяем временной диапазон "сегодня"
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)

        # Получаем все действия пользователя за день
        actions = Action.query.filter(
            and_(
                Action.user_id == user_id,
                Action.datetime >= today_start,
                Action.datetime < today_end
            )
        ).all()

        # Подсчёт по категориям действий
        right = sum(a.action == Action.RIGHT_ANSWER for a in actions)
        wrong = sum(a.action == Action.WRONG_ANSWER for a in actions)
        skipped = sum(a.action == Action.SKIP for a in actions)

        total = right + wrong + skipped

        if total == 0:
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton('Решать', web_app=types.WebAppInfo(url=app.config.get('URL')))
            markup.add(button)
            try:
                bot.send_message(user_id, "<b>Итоги дня</b>\n\nКажется, сегодня ничего нет. Давай решим хотя бы пару заданий?", reply_markup=markup)
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
            text += (
                '\n\nОтличный результат! Продолжай в том же духе!'
            )

        bot.send_message(user_id, text)


def send_all_message(text):
    success, fail = 0, 0
    with app.app_context():
        users = Settings.query.all()
        for user in users:
            try:
                bot.send_message(user.user_id, text)
                success += 1
            except:
                fail += 1
            sleep(.5)
    
    bot.send_message(os.getenv('ADMIN_ID'), f'Отправлено\nУспешно: {success}\nОшибки: {fail}')