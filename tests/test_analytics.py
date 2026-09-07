import csv
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO

from app.extensions import db
from app.models import Action, User
from app.services.analytics import build_dashboard, parse_filters
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
        assert self.client.get("/admin/analytics").status_code == 403
        assert self.client.get("/admin/analytics.csv").status_code == 403
        assert self.client.get("/api/v1/admin/analytics/items/1").status_code == 403
        assert self.client.get("/api/v1/admin/analytics/exercises").status_code == 403
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
        assert summary["right"] == 3
        assert summary["wrong"] == 1
        assert summary["skips"] == 1
        assert summary["accuracy"] == 75.0
        assert summary["sessions"] == 4
        assert summary["active_seconds"] == 1200
        assert summary["retention"]["d1"]["retained"] == 1
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
        rows = list(csv.reader(StringIO(response.data.decode("utf-8-sig"))))

        assert rows[1][1] == "'+SUM(A1:A2)"
        assert rows[1][4].startswith("'=HYPERLINK")

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
