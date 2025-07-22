from app import app
from app.models import Category
from app.utils import get_strike

from flask import render_template, session


@app.route('/task/<int:task_id>')
def task(task_id):
    return render_template('index.html', strike=session.get('strike', get_strike(session.get('user_id'))),
                           params=f'task_id={task_id}')


@app.route('/category/<int:category_id>')
def category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return 'Category not found', 404
    return render_template('index.html', strike=session.get('strike', get_strike(session.get('user_id'))),
                           params=f'category_id={category_id}')


@app.route('/mistakes')
def mistakes():
    if 'user_id' not in session:
        return 'Not authenticated', 401

    return render_template('index.html', strike=session.get('strike', 0, get_strike(session.get('user_id'))),
                           params=f'mistakes=true')


@app.route('/filters')
def filters():
    categories = Category.query.all()
    return render_template('filters.html', categories=categories, tasks=app.config['TASKS'])