from app import app
from app.models import Action
from app.utils import get_cached_strike

from flask import jsonify, request, send_file
from flask_login import current_user, login_required
import os
import random


@app.route('/get_background')
@login_required
def get_background():
    user = current_user

    strike = get_cached_strike(user.id)

    levels = app.config['STRIKE_LEVELS']

    if strike < levels[0] or not user.settings.strike:
        path = 'dark'
    elif strike < levels[1]:
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
@login_required
def can_swipe():
    user = current_user
    word_id = request.args.get('word_id')

    if not user.settings.strike:
        return jsonify({'status': 'yes'}), 200

    if word_id is None:
        return jsonify({'status': 'error', 'message': 'No word id'}), 401

    try:
        word_id = int(word_id)
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid word id'}), 400

    last_words = (
        Action.query
        .filter(Action.user_id == user.id)
        .order_by(Action.datetime.desc())
        .limit(3)
    )
    last_ids = [e.word_id for e in last_words]
    strike = get_cached_strike(user.id)

    if word_id in last_ids or strike <= 3:
        return jsonify({'status': 'yes'}), 200
    else:
        return jsonify({'status': 'no'}), 200


# @app.after_request
# def add_cache_control_headers(response):
#     if request.path.endswith('.css') or request.path.endswith('.js'):
#         response.headers['Cache-Control'] = 'public, max-age=31536000'
#     return response
