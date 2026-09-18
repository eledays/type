from __future__ import annotations

from pathlib import Path

from flask_migrate import downgrade, upgrade
from sqlalchemy import text

from app import create_app
from app.extensions import db
from app.models import Action, Category, Settings, SpellingExercise, User


def test_latest_migration_round_trip_preserves_existing_actions(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migrations.sqlite3"
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
        "RATELIMIT_STORAGE_URI": "memory://",
        "LEGAL_CONSENT_REQUIRED": False,
    })
    with app.app_context():
        upgrade(directory="migrations")
        category = Category(name="Migration")
        user = User(yandex_id="migration-user", settings=Settings())
        word = SpellingExercise(
            word="пров_рка",
            answers=["е", "и"],
            correct_answer="е",
            category=category,
        )
        db.session.add_all([user, word])
        db.session.flush()
        db.session.add(Action(
            user_id=user.id,
            practice_item_id=word.id,
            action=Action.RIGHT_ANSWER,
            request_id="migration-action",
        ))
        db.session.commit()

        downgrade(directory="migrations", revision="-1")
        columns = {
            row[1] for row in db.session.execute(text("PRAGMA table_info(action)"))
        }
        assert "request_id" not in columns
        assert db.session.scalar(text("SELECT COUNT(*) FROM action")) == 1

        upgrade(directory="migrations")
        columns = {
            row[1] for row in db.session.execute(text("PRAGMA table_info(action)"))
        }
        assert "request_id" in columns
        assert db.session.scalar(text("SELECT COUNT(*) FROM action")) == 1
