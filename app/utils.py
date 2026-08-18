from app.extensions import db
from app.models import Action, User

from datetime import datetime, timedelta
from pathlib import Path

from flask import current_app, session
from sqlalchemy import desc, select
from sqlalchemy.engine import make_url


def add_action(
    user_id: int,
    word_id: int | None,
    action: int,
) -> Action:
    action_record = Action()
    action_record.user_id = user_id
    action_record.word_id = word_id
    action_record.action = action
    db.session.add(action_record)
    db.session.commit()
    return action_record


def get_anonymous_actions_remaining(user: User) -> int | None:
    """Return a guest quota, or ``None`` for a registered account."""
    if not user.is_anonymous_account:
        return None
    used = db.session.scalar(
        select(db.func.count(Action.id)).where(
            Action.user_id == user.id,
            Action.action.in_([
                Action.RIGHT_ANSWER,
                Action.WRONG_ANSWER,
                Action.SKIP,
            ]),
        )
    ) or 0
    limit = int(current_app.config["ANONYMOUS_ACTION_LIMIT"])
    return max(0, limit - used)


def do_backup():
    """Export the current database when the scheduler is run explicitly."""
    from db_to_json import export_to_json

    database_url = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"])
    if database_url.get_backend_name() != "sqlite" or not database_url.database:
        raise RuntimeError(
            "JSON backups are supported only for file-based SQLite databases."
        )

    database_path = Path(database_url.database)
    if not database_path.is_absolute():
        database_path = Path(current_app.instance_path) / database_path

    if not database_path.is_file():
        raise FileNotFoundError(
            "Database does not exist. Run `flask --app app db upgrade` first."
        )

    backup_directory = Path(current_app.config["BACKUP_PATH"])
    backup_directory.mkdir(parents=True, exist_ok=True)
    backup_path = backup_directory / f'{datetime.now():%Y-%m-%d_%H-%M-%S}.json'
    export_to_json(str(database_path), str(backup_path))


def get_strike(user_id: int) -> int:
    actions = db.session.scalars(
        select(Action.action)
        .where(
            Action.user_id == user_id,
            Action.action.in_([
                Action.RIGHT_ANSWER,
                Action.WRONG_ANSWER,
                Action.SKIP,
            ]),
        )
        .order_by(desc(Action.datetime))
    )

    streak = 0
    for action in actions:
        if action == Action.RIGHT_ANSWER:
            streak += 1
        else:
            break

    return streak


def get_cached_strike(user_id: int) -> int:
    """Return the streak stored in the session, loading it only when absent."""
    if "strike" not in session:
        session["strike"] = get_strike(user_id)
    return int(session["strike"])


def get_user_stats(user_id: int) -> dict[str, int | float]:
    actions = db.session.execute(
        select(Action.action, Action.datetime)
        .where(
            Action.user_id == user_id,
            Action.action.in_([
                Action.RIGHT_ANSWER,
                Action.WRONG_ANSWER,
                Action.SKIP,
            ]),
        )
        .order_by(Action.datetime)
    )

    mistakes = 0
    skips = 0
    correct = 0
    best_streak = 0
    current_streak = 0

    total_time = timedelta()
    last_time = None
    timed_intervals = 0
    max_pause = timedelta(minutes=10)

    for action in actions:
        if last_time is not None:
            pause = action.datetime - last_time
            if pause <= max_pause:
                total_time += pause
                timed_intervals += 1
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

    answered = correct + mistakes
    percent_correct = (correct / answered * 100) if answered else 0
    average_seconds = (
        total_time.total_seconds() / timed_intervals
        if timed_intervals
        else 0
    )

    return {
        "correct": correct,
        "mistakes": mistakes,
        "skips": skips,
        "correct_percent": round(percent_correct, 1),
        "avg_time_per_word": round(average_seconds, 1),
        "best_streak": best_streak,
    }
