from app import app
from app.models import Action, Settings
from app.utils import get_strike

from flask import jsonify, request, send_file, session
import os
import random


@app.route('/get_background')
def get_background():
    user_id = session.get('user_id', None)
    user_settings = Settings.query.filter(Settings.user_id == user_id).first()

    if 'strike' not in session and user_id:
        session['strike'] = get_strike(user_id)

    levels = app.config['STRIKE_LEVELS']

    if user_id is None:
        path = 'dark'
    elif str(user_id) in [str(os.getenv('SECURE_ID')), str(os.getenv('ADMIN_ID'))] and session['strike'] >= levels[0]:
        filename = random.choice(os.listdir(f'app/secure_static/backs/'))
        response = send_file(f'secure_static/backs/{filename}')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    elif session['strike'] < levels[0] or not user_settings.strike:
        path = 'dark'
    elif session['strike'] < levels[1]:
        path = 'yellow'
    else:
        path = 'dark'

    filename = random.choice(os.listdir(f'app/static/img/backs/{path}'))
    response = send_file(f'static/img/backs/{path}/{filename}')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/favicon.ico')
def favicon():
    return send_file('static/img/fav.ico', mimetype='image/x-icon')


@app.route('/can_swipe', methods=['GET'])
def can_swipe():
    user_id = session.get('user_id', None)
    user_settings = Settings.query.filter(Settings.user_id == user_id).first() if user_id else None
    word_id = request.args.get('word_id')

    if user_settings is None:
        return jsonify({'status': 'yes'}), 200

    if not user_settings.strike:
        return jsonify({'status': 'yes'}), 200

    if word_id is None:
        return jsonify({'status': 'error', 'message': 'No word id'}), 401

    word_id = int(word_id)
    last_words = Action.query.filter(Action.user_id == user_id).order_by(Action.datetime.desc()).limit(3)
    last_ids = [e.word_id for e in last_words]
    strike = session.get('strike', get_strike(user_id))

    if word_id in last_ids or strike <= 3:
        return jsonify({'status': 'yes'}), 200
    else:
        return jsonify({'status': 'no'}), 200


# @app.after_request
# def add_cache_control_headers(response):
#     if request.path.endswith('.css') or request.path.endswith('.js'):
#         response.headers['Cache-Control'] = 'public, max-age=31536000'
#     return response
