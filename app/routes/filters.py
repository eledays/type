from app.extensions import db
from app.models import Category
from app.utils import get_cached_strike

from flask import Blueprint, current_app, render_template
from flask_login import current_user, login_required


bp = Blueprint("filters", __name__)


@bp.route('/task/<int:task_id>')
@login_required
def task(task_id):
    user = current_user
    return render_template('index.html', strike=get_cached_strike(user.id),
                           params=f'task_id={task_id}')


@bp.route('/category/<int:category_id>')
@login_required
def category(category_id):
    user = current_user
    category = db.session.get(Category, category_id)
    if not category:
        return 'Category not found', 404
    return render_template('index.html', strike=get_cached_strike(user.id),
                           params=f'category_id={category_id}')


@bp.route('/mistakes')
@login_required
def mistakes():
    user = current_user
    return render_template('index.html', strike=get_cached_strike(user.id),
                           params=f'mistakes=true')


@bp.route('/filters')
def filters():
    categories = Category.query.all()
    return render_template(
        'filters.html',
        categories=categories,
        tasks=current_app.config['TASKS'],
    )
