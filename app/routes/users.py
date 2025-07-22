from app import app, db, ENABLE_TELEGRAM
from app.models import Word, Settings
from app.utils import get_user_stats

from flask import render_template, jsonify, request, session

if ENABLE_TELEGRAM:
    from app import bot
    from init_data_py import InitData
    import telebot

import datetime
import os

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return render_template('auth.html')

    user_id = session.get('user_id')
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()

    if user_settings is None:
        user_settings = Settings(user_id=user_id)
        db.session.add(user_settings)
        db.session.commit()

    admin = str(user_id) == str(os.getenv('ADMIN_ID'))
    if admin and session.get('admin', False):
        admin = 2
    elif admin and not session.get('admin', False):
        admin = 1

    stats = get_user_stats(user_id)
    if admin:
        stats["explanations"] = Word.query.filter(Word.explanation.isnot(None)).count()
        stats["users"] = Settings.query.count()

    return render_template('settings.html', settings=user_settings, admin=admin, stats=stats)


@app.route('/set_settings', methods=['POST'])
def set_settings():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401

    user_id = session.get('user_id')
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()

    if 'admin' in request.json and str(user_id) == str(os.getenv('ADMIN_ID')):
        session['admin'] = request.json.get('admin')
        return 'ok', 200

    for k, v in request.json.items():
        if hasattr(user_settings, k):
            if k.endswith('_time'):
                v = datetime.datetime.strptime(v, '%H:%M').time()
            setattr(user_settings, k, v)
        else:
            db.session.rollback()
            return 'Unknown field', 400
    db.session.commit()

    return 'ok', 200


@app.route('/set_user_id', methods=['POST'])
def set_user_id():
    if ENABLE_TELEGRAM:
        return jsonify({'status': 'error'}), 400
    user_id = request.json.get('user_id')
    if user_id is not None:
        session['user_id'] = user_id
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error'}), 400


@app.route('/verify_hash', methods=['POST'])
def verify_hash():
    if not ENABLE_TELEGRAM:
        return 'No Telegram integration', 500

    data = request.get_json()
    init_data = InitData.parse(data.get('initData', ''))

    if init_data.validate(os.getenv('BOT_TOKEN')):
        session['user_id'] = init_data.user.id
        print(session.get('user_id'))
        return jsonify({'valid': True}), 200
    else:
        session['user_id'] = None
        return jsonify({'valid': False}), 400
    

@app.route('/tg_webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Error', 501