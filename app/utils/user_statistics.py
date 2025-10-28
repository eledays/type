from app import app
from app.models import Action

from datetime import timedelta
from sqlalchemy import desc


def get_user_stats(user_id: int):
    with app.app_context():
        actions = (
            Action.query.filter(
                Action.user_id == user_id,
                Action.action.in_(
                    [Action.RIGHT_ANSWER, Action.WRONG_ANSWER, Action.SKIP]
                ),
            )
            .order_by(Action.datetime)
            .all()
        )

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
            "best_streak": best_streak,
        }


def get_strike(user_id):
    with app.app_context():
        actions = (
            Action.query.filter(
                Action.user_id == user_id,
                Action.action.in_(
                    [Action.RIGHT_ANSWER, Action.WRONG_ANSWER, Action.SKIP]
                ),
            )
            .order_by(desc(Action.datetime))
            .all()
        )

        streak = 0
        for action in actions:
            if action.action == Action.RIGHT_ANSWER:
                streak += 1
            else:
                break

        return streak
