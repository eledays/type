from __future__ import annotations

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier

import pytest
from sqlalchemy.engine import make_url

from app import create_app
from app.extensions import db
from app.models import Action, Category, Settings, SpellingExercise, User
from app.services.analytics import build_dashboard, parse_filters
from app.services.practice import PracticeError, check_answer


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


def test_postgres_serializes_anonymous_quota(postgres_database) -> None:
    """Only one of two simultaneous final guest attempts may be recorded."""
    # Flask-SQLAlchemy 3 exposes the active application through current_app;
    # retain a concrete reference before worker threads create their contexts.
    from flask import current_app

    app = current_app._get_current_object()
    app.config["ANONYMOUS_ACTION_LIMIT"] = 1
    user = User(settings=Settings())
    word = SpellingExercise(
        word="к_нкурентный",
        answers=["о", "а"],
        correct_answer="о",
        category=Category(name="Concurrency"),
    )
    db.session.add_all([user, word])
    db.session.commit()
    user_id = user.id
    word_id = word.id
    barrier = Barrier(2)

    def submit(request_id: str) -> str:
        with app.test_request_context("/api/v1/attempts", method="POST"):
            local_user = db.session.get(User, user_id)
            barrier.wait(timeout=5)
            try:
                check_answer(
                    local_user,
                    word_id,
                    "о",
                    "spelling",
                    request_id=request_id,
                )
            except PracticeError as error:
                db.session.rollback()
                return error.code
            finally:
                db.session.remove()
            return "created"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, ("parallel-1", "parallel-2")))

    assert sorted(results) == ["anonymous_limit_reached", "created"]
    assert Action.query.filter_by(user_id=user_id).count() == 1
