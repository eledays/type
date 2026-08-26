import os

import pytest


os.environ["DEBUG"] = "false"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-test-suite-32chars")
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "redis://localhost:6379/15")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Category, Settings, SpellingExercise, User  # noqa: E402


class AppTestCase:
    """Application fixture with an isolated database and browser session."""

    @pytest.fixture(autouse=True)
    def app_context(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "ANONYMOUS_ACTION_LIMIT": 3,
            "SERVER_NAME": "localhost",
            "TRUSTED_HOSTS": ["localhost"],
            "RATELIMIT_STORAGE_URI": "memory://",
            "WTF_CSRF_ENABLED": False,
        })
        with self.app.app_context():
            db.create_all()
        self.client = self.app.test_client()
        yield
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def current_user_id(self) -> int:
        self.client.get("/")
        with self.client.session_transaction() as browser_session:
            return int(browser_session["_user_id"])

    def make_user(self, **values) -> User:
        user = User(**values)
        user.settings = Settings()
        db.session.add(user)
        db.session.commit()
        return user

    def make_word(
        self,
        word: str = "м_локо",
        answers: list[str] | None = None,
        correct_answer: str = "о",
        task_number: int | None = 4,
        category_name: str = "Орфография",
    ) -> SpellingExercise:
        category = Category.query.filter_by(name=category_name).first()
        if category is None:
            category = Category()
            category.name = category_name
            db.session.add(category)
        model = SpellingExercise()
        model.word = word
        model.answers = answers or ["о", "а"]
        model.correct_answer = correct_answer
        model.task_number = task_number
        model.category = category
        db.session.add(model)
        db.session.commit()
        return model
