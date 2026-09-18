import csv
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO

import pytest
from sqlalchemy import event

from app.extensions import db
from app.models import Action, Category, SpellingExercise, User
from app.routes.admin.pages import _csv_safe
from app.services.analytics import (
    build_dashboard,
    build_exercise_results,
    parse_filters,
)
from tests.base import AppTestCase


class TestAnalytics(AppTestCase):
    def _make_admin(self) -> int:
        user_id = self.current_user_id()
        with self.app.app_context():
            user = db.session.get(User, user_id)
            user.is_admin = True
            user.yandex_id = "analytics-admin"
            user.identified_at = datetime.now()
            db.session.commit()
        return user_id

    def test_dashboard_and_exports_require_database_admin(self) -> None:
        assert self.client.get("/admin/analytics").status_code == 302
        assert self.client.get("/admin/analytics.csv").status_code == 302
        assert self.client.get(
            "/api/v1/admin/analytics/items/1"
        ).status_code == 401
        assert self.client.get(
            "/api/v1/admin/analytics/exercises"
        ).status_code == 401
        assert "Перейти в аналитику".encode() not in self.client.get("/").data

        self._make_admin()
        page = self.client.get("/admin/analytics")

        assert page.status_code == 200
        assert "Общая сводка".encode() in page.data
        assert "Удержание".encode() in page.data
        assert "Аналитика заданий".encode() in page.data
        assert "Перейти в аналитику".encode() in self.client.get("/").data

    def test_summary_sessions_retention_and_conversion(self) -> None:
        self._make_admin()
        today = date.today()
        cohort_day = today - timedelta(days=31)
        with self.app.app_context():
            learner = self.make_user(
                created_at=datetime.combine(cohort_day, time(hour=9)),
                identified_at=datetime.combine(
                    cohort_day + timedelta(days=2), time(hour=10)
                ),
                yandex_id="retained-learner",
            )
            word = self.make_word()
            for offset, minute, action in (
                (1, 0, Action.RIGHT_ANSWER),
                (1, 20, Action.WRONG_ANSWER),
                (1, 55, Action.SKIP),
                (7, 0, Action.RIGHT_ANSWER),
                (30, 0, Action.RIGHT_ANSWER),
            ):
                db.session.add(Action(
                    user_id=learner.id,
                    practice_item_id=word.id,
                    action=action,
                    datetime=datetime.combine(
                        cohort_day + timedelta(days=offset),
                        time(hour=11, minute=minute),
                    ),
                ))
            db.session.commit()

            filters = parse_filters({
                "period": "custom",
                "start": cohort_day.isoformat(),
                "end": today.isoformat(),
                "user_type": "registered",
            })
            dashboard = build_dashboard(filters)

        summary = dashboard["summary"]
        assert summary["right"] == 2
        assert summary["wrong"] == 0
        assert summary["skips"] == 0
        assert summary["accuracy"] == 100.0
        assert summary["sessions"] == 2
        assert summary["active_seconds"] == 0
        assert summary["retention"]["d1"]["retained"] == 0
        assert summary["retention"]["d7"]["retained"] == 1
        assert summary["retention"]["d30"]["retained"] == 1
        assert summary["conversions"] == 1

    def test_user_total_respects_type_and_historical_end(self) -> None:
        with self.app.app_context():
            self.make_user(
                yandex_id="registered-before-end",
                created_at=datetime(2026, 1, 1, 12),
            )
            self.make_user(created_at=datetime(2026, 1, 1, 13))
            self.make_user(
                yandex_id="registered-after-end",
                created_at=datetime(2026, 1, 3, 12),
            )
            filters = parse_filters({
                "period": "custom",
                "start": "2026-01-01",
                "end": "2026-01-02",
                "user_type": "registered",
            })
            dashboard = build_dashboard(filters)

        assert dashboard["summary"]["total_users"] == 1
        assert dashboard["summary"]["audience_label"] == (
            "Авторизованные к концу периода"
        )

    def test_user_type_is_evaluated_at_action_time(self) -> None:
        with self.app.app_context():
            learner = self.make_user(
                yandex_id="identified-later",
                created_at=datetime(2026, 1, 1, 10),
                identified_at=datetime(2026, 1, 2, 10),
            )
            word = self.make_word()
            db.session.add_all([
                Action(
                    user_id=learner.id,
                    practice_item_id=word.id,
                    action=Action.RIGHT_ANSWER,
                    datetime=datetime(2026, 1, 1, 12),
                ),
                Action(
                    user_id=learner.id,
                    practice_item_id=word.id,
                    action=Action.WRONG_ANSWER,
                    datetime=datetime(2026, 1, 2, 12),
                ),
            ])
            db.session.commit()
            registered = build_dashboard(parse_filters({
                "period": "custom",
                "start": "2026-01-01",
                "end": "2026-01-02",
                "user_type": "registered",
            }))
            anonymous = build_dashboard(parse_filters({
                "period": "custom",
                "start": "2026-01-01",
                "end": "2026-01-02",
                "user_type": "anonymous",
            }))

        assert registered["summary"]["right"] == 0
        assert registered["summary"]["wrong"] == 1
        assert anonymous["summary"]["right"] == 1
        assert anonymous["summary"]["wrong"] == 0

    def test_filters_item_detail_and_csv(self) -> None:
        self._make_admin()
        with self.app.app_context():
            learner = self.make_user(yandex_id="content-learner")
            word = self.make_word(task_number=4)
            other = self.make_word(word="к_рова", task_number=10)
            db.session.add_all([
                Action(
                    user_id=learner.id,
                    practice_item_id=word.id,
                    action=Action.WRONG_ANSWER,
                ),
                Action(
                    user_id=learner.id,
                    practice_item_id=other.id,
                    action=Action.RIGHT_ANSWER,
                ),
            ])
            db.session.commit()
            word_id = word.id

        page = self.client.get("/admin/analytics?task=4&period=7")
        assert page.status_code == 200
        assert "м_локо".encode() in page.data
        assert "к_рова".encode() not in page.data

        detail = self.client.get(
            f"/api/v1/admin/analytics/items/{word_id}?period=7"
        )
        assert detail.status_code == 200
        assert detail.get_json()["wrong"] == 1
        assert detail.get_json()["accuracy"] == 0.0

        export = self.client.get("/admin/analytics.csv?task=4&period=7")
        assert export.status_code == 200
        assert export.mimetype == "text/csv"
        assert "м_локо".encode() in export.data
        assert "к_рова".encode() not in export.data

    def test_exercises_are_limited_and_searchable(self) -> None:
        self._make_admin()
        with self.app.app_context():
            learner = self.make_user(yandex_id="search-learner")
            for index in range(12):
                word = self.make_word(word=f"термин{index}")
                db.session.add(Action(
                    user_id=learner.id,
                    practice_item_id=word.id,
                    action=Action.RIGHT_ANSWER,
                ))
            db.session.commit()

        page = self.client.get("/admin/analytics?period=7")

        assert page.status_code == 200
        assert page.data.count(b"data-item-id=") == 10
        assert "Упражнения".encode() in page.data
        assert "Показано 10 из 12".encode() in page.data

        search = self.client.get(
            "/admin/analytics",
            query_string={"period": "7", "exercise_query": "11"},
        )

        assert search.status_code == 200
        assert search.data.count(b"data-item-id=") == 1
        assert "термин11".encode() in search.data
        assert "Показано 1 из 1".encode() in search.data

    def test_live_search_treats_exercise_blank_as_a_letter(self) -> None:
        self._make_admin()
        with self.app.app_context():
            learner = self.make_user(yandex_id="fuzzy-search-learner")
            word = self.make_word(word="экз_менатор")
            db.session.add(Action(
                user_id=learner.id,
                practice_item_id=word.id,
                action=Action.WRONG_ANSWER,
            ))
            db.session.commit()

        response = self.client.get(
            "/api/v1/admin/analytics/exercises",
            query_string={"period": "7", "exercise_query": "экзаме"},
        )

        assert response.status_code == 200
        assert response.get_json()["item_count"] == 1
        assert response.get_json()["items"][0]["title"] == "экз_менатор"

    def test_live_search_rejects_short_or_punctuation_only_queries(self) -> None:
        self._make_admin()
        for query in ("а", "___", "!? "):
            response = self.client.get(
                "/api/v1/admin/analytics/exercises",
                query_string={"period": "7", "exercise_query": query},
            )
            assert response.status_code == 400
            assert response.get_json()["error"] == "query_too_short"

    def test_csv_escapes_spreadsheet_formulas(self) -> None:
        self._make_admin()
        with self.app.app_context():
            learner = self.make_user(yandex_id="csv-learner")
            word = self.make_word(
                word="+SUM(A1:A2)",
                category_name="=HYPERLINK(\"https://example.com\")",
            )
            db.session.add(Action(
                user_id=learner.id,
                practice_item_id=word.id,
                action=Action.RIGHT_ANSWER,
            ))
            db.session.commit()

        response = self.client.get("/admin/analytics.csv?period=7")
        assert response.is_streamed
        rows = list(csv.reader(StringIO(response.data.decode("utf-8-sig"))))

        assert rows[1][1] == "'+SUM(A1:A2)"
        assert rows[1][4].startswith("'=HYPERLINK")

    @pytest.mark.parametrize("prefix", [
        " ", "\t", "\n", "\ufeff", "\u200b", " \ufeff\u200b",
    ])
    def test_csv_formula_sanitization_ignores_leading_controls(
        self,
        prefix: str,
    ) -> None:
        value = f"{prefix}=SUM(A1:A2)"
        assert _csv_safe(value) == f"'{value}"

    def test_calendar_days_use_configured_timezone(self) -> None:
        with self.app.app_context():
            learner = self.make_user(yandex_id="timezone-learner")
            word = self.make_word()
            db.session.add(Action(
                user_id=learner.id,
                practice_item_id=word.id,
                action=Action.RIGHT_ANSWER,
                datetime=datetime(
                    2026, 1, 1, 21, 30, tzinfo=timezone.utc
                ),
            ))
            db.session.commit()
            filters = parse_filters({
                "period": "custom",
                "start": "2026-01-02",
                "end": "2026-01-02",
            })
            dashboard = build_dashboard(filters)

        assert filters.start_at == datetime(
            2026, 1, 1, 21, 0, tzinfo=timezone.utc
        )
        assert dashboard["daily"][0]["date"] == "2026-01-02"
        assert dashboard["daily"][0]["right"] == 1

    def test_sqlite_calendar_days_follow_dst_per_timestamp(self) -> None:
        self.app.config["ANALYTICS_TIMEZONE"] = "Europe/Berlin"
        with self.app.app_context():
            learner = self.make_user(yandex_id="dst-learner")
            word = self.make_word()
            db.session.add(Action(
                user_id=learner.id,
                practice_item_id=word.id,
                action=Action.RIGHT_ANSWER,
                datetime=datetime(2026, 3, 29, 22, 30, tzinfo=timezone.utc),
            ))
            db.session.commit()
            dashboard = build_dashboard(parse_filters({
                "period": "custom",
                "start": "2026-03-29",
                "end": "2026-03-30",
            }))

        assert dashboard["daily"][0]["right"] == 0
        assert dashboard["daily"][1]["right"] == 1

    def test_session_boundary_uses_previous_action(self) -> None:
        with self.app.app_context():
            learner = self.make_user(yandex_id="boundary-learner")
            word = self.make_word()
            db.session.add_all([
                Action(
                    user_id=learner.id,
                    practice_item_id=word.id,
                    action=Action.RIGHT_ANSWER,
                    datetime=datetime(2026, 1, 1, 20, 50),
                ),
                Action(
                    user_id=learner.id,
                    practice_item_id=word.id,
                    action=Action.RIGHT_ANSWER,
                    datetime=datetime(2026, 1, 1, 21, 10),
                ),
            ])
            db.session.commit()
            summary = build_dashboard(parse_filters({
                "period": "custom",
                "start": "2026-01-02",
                "end": "2026-01-02",
            }))["summary"]

        assert summary["cards"] == 1
        assert summary["sessions"] == 0
        assert summary["active_seconds"] == 1200

    def test_exercise_results_use_a_bounded_number_of_queries(self) -> None:
        with self.app.app_context():
            learner = self.make_user(yandex_id="large-analytics-user")
            category = Category(name="Нагрузка")
            exercises = [
                SpellingExercise(
                    word=f"нагрузка{index}",
                    answers=["а", "о"],
                    correct_answer="а",
                    task_number=9,
                    category=category,
                )
                for index in range(250)
            ]
            db.session.add_all(exercises)
            db.session.flush()
            db.session.execute(Action.__table__.insert(), [
                {
                    "user_id": learner.id,
                    "practice_item_id": exercise.id,
                    "action": Action.RIGHT_ANSWER,
                    "datetime": datetime.now(timezone.utc),
                }
                for exercise in exercises
                for _ in range(10)
            ])
            db.session.commit()
            filters = parse_filters({"period": "7"})
            statements = []

            def count_query(*args) -> None:
                statements.append(args[2])

            engine = db.session.get_bind()
            event.listen(engine, "before_cursor_execute", count_query)
            try:
                result = build_exercise_results(filters)
            finally:
                event.remove(engine, "before_cursor_execute", count_query)

        assert result["item_count"] == 250
        assert len(result["items"]) == 10
        assert len(statements) <= 3

        with self.app.app_context():
            statements.clear()
            engine = db.session.get_bind()
            event.listen(engine, "before_cursor_execute", count_query)
            try:
                dashboard = build_dashboard(filters)
            finally:
                event.remove(engine, "before_cursor_execute", count_query)

        assert dashboard["content"]["item_count"] == 250
        assert len(statements) <= 15
