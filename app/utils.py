from app import app, db, bot
from app.models import Action, Settings

from telebot import types

from datetime import datetime, time, timedelta
from sqlalchemy import or_, desc


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

        else:
            users_to_notify = Settings.query.filter(
                Settings.notification == True,
                or_(
                    Settings.notification_time >= start,
                    Settings.notification_time < end
                )
            ).all()

        today_start = datetime.combine(datetime.now().date(), time(0, 0))
        active_user_ids = db.session.query(Action.user_id).filter(
            Action.datetime >= today_start
        ).distinct().all()
        active_user_ids = {uid for uid, in active_user_ids}

        for user in users_to_notify:
            # if user.user_id in active_user_ids:
            #     continue
            
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton('Поехали', web_app=types.WebAppInfo(url=app.config.get('URL')))
            markup.add(button)

            bot.send_message(user.user_id, 'Привет! Пора русский порешать', reply_markup=markup)


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
