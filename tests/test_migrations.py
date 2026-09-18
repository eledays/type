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

        downgrade(directory="migrations", revision="4b8f1a2c6d90")
        columns = {
            row[1]: row
            for row in db.session.execute(text("PRAGMA table_info(action)"))
        }
        assert columns["request_id"][3] == 0
        user_columns = {
            row[1] for row in db.session.execute(text('PRAGMA table_info("user")'))
        }
        assert "last_seen_at" not in user_columns
        db.session.execute(text(
            "UPDATE action SET request_id = NULL WHERE id = :action_id"
        ), {"action_id": db.session.scalar(text("SELECT id FROM action"))})
        db.session.commit()
        assert db.session.scalar(text("SELECT COUNT(*) FROM action")) == 1

        upgrade(directory="migrations")
        columns = {
            row[1]: row
            for row in db.session.execute(text("PRAGMA table_info(action)"))
        }
        assert columns["request_id"][3] == 1
        assert db.session.scalar(text(
            "SELECT request_id FROM action"
        )).startswith("legacy-")
        user_columns = {
            row[1]: row
            for row in db.session.execute(text('PRAGMA table_info("user")'))
        }
        assert user_columns["last_seen_at"][3] == 1
        assert db.session.scalar(text("SELECT COUNT(*) FROM action")) == 1
