from app import app, db
from app.models import Action


def add_action(user_id, word_id, action):
    if user_id is None or action is None:
        return None
    action = Action(user_id=user_id, word_id=word_id, action=action)
    db.session.add(action)
    db.session.commit()