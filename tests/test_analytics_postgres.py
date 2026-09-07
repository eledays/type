from __future__ import annotations

from datetime import datetime, timezone
import os

import pytest
from sqlalchemy.engine import make_url

from app import create_app
from app.extensions import db
from app.models import Action, Category, Settings, SpellingExercise, User
from app.services.analytics import build_dashboard, parse_filters


POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")
POSTGRES_ENABLED = (
    os.environ.get("ALLOW_POSTGRES_TESTS") == "1"
    and POSTGRES_URL is not None
    and make_url(POSTGRES_URL).database is not None
    and make_url(POSTGRES_URL).database.endswith("_test")
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not POSTGRES_ENABLED,
        reason="Set ALLOW_POSTGRES_TESTS=1 and a *_test TEST_POSTGRES_URL",
    ),
]


@pytest.fixture
def postgres_database():
    """Create and always clean a schema in the dedicated test database."""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": POSTGRES_URL,
        "ANALYTICS_TIMEZONE": "Europe/Moscow",
        "RATELIMIT_STORAGE_URI": "memory://",
    })
    with app.app_context():
        db.drop_all()
        db.create_all()
        try:
            yield
        finally:
            db.session.remove()
            db.drop_all()


def test_postgres_analytics_queries_and_timezone(postgres_database) -> None:
    """Exercise PostgreSQL-specific date and interval expressions."""
    assert postgres_database is None
    category = Category(name="PostgreSQL")
    word = SpellingExercise(
        word="пров_рка",
        answers=["е", "и"],
        correct_answer="е",
        task_number=9,
        category=category,
    )
    user = User(yandex_id="postgres-user", settings=Settings())
    db.session.add_all([word, user])
    db.session.flush()
    db.session.add_all([
        Action(
            user_id=user.id,
            practice_item_id=word.id,
            action=Action.RIGHT_ANSWER,
            datetime=datetime(2026, 1, 1, 21, 5, tzinfo=timezone.utc),
        ),
        Action(
            user_id=user.id,
            practice_item_id=word.id,
            action=Action.WRONG_ANSWER,
            datetime=datetime(2026, 1, 1, 21, 25, tzinfo=timezone.utc),
        ),
    ])
    db.session.commit()

    filters = parse_filters({
        "period": "custom",
        "start": "2026-01-02",
        "end": "2026-01-02",
    })
    dashboard = build_dashboard(filters)

    assert dashboard["daily"][0]["cards"] == 2
    assert dashboard["summary"]["sessions"] == 1
    assert dashboard["summary"]["active_seconds"] == 1200
