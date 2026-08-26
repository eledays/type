from bs4 import BeautifulSoup

from tests.base import AppTestCase

from app.extensions import db
from app.models import User


class TestCSRFProtection(AppTestCase):
    def enable_csrf(self) -> None:
        self.app.config["WTF_CSRF_ENABLED"] = True

    def page_token(self, path: str = "/") -> str:
        response = self.client.get(path)
        page = BeautifulSoup(response.data, "html.parser")
        field = page.select_one('input[name="csrf_token"]')
        assert field is not None
        return str(field["value"])

    def test_all_rendered_forms_contain_csrf_field(self) -> None:
        user_id = self.current_user_id()
        with self.app.app_context():
            db.session.get(User, user_id).yandex_id = "registered-user"
            db.session.commit()

        for path in ("/", "/profile"):
            page = BeautifulSoup(self.client.get(path).data, "html.parser")
            forms = page.select("form")
            assert forms
            assert all(
                form.select_one('input[name="csrf_token"]') is not None
                for form in forms
            )

    def test_mutating_requests_reject_missing_or_invalid_token(self) -> None:
        self.enable_csrf()
        self.client.get("/")

        for headers in ({}, {"X-CSRFToken": "invalid-token"}):
            response = self.client.patch(
                "/api/v1/profile/settings",
                json={"strike": False},
                headers=headers,
            )
            assert response.status_code == 400
            assert response.get_json()["error"] == "csrf_failed"

        logout = self.client.post("/auth/logout")
        assert logout.status_code == 400

    def test_same_session_token_protects_html_forms_and_json_api(self) -> None:
        self.enable_csrf()
        token = self.page_token()

        api_response = self.client.patch(
            "/api/v1/profile/settings",
            json={"strike": False},
            headers={"X-CSRFToken": token},
        )
        form_response = self.client.post(
            "/auth/logout", data={"csrf_token": token}
        )

        assert api_response.status_code == 200
        assert form_response.status_code == 302
