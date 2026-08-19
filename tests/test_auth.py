from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.base import AppTestCase

from app.extensions import db
from app.models import Action, User
from app.services.auth import OAuthError, authenticate_yandex, safe_next_url, validate_state


class TestAuth(AppTestCase):
    def test_next_url_allows_local_paths_only(self) -> None:
        with self.app.test_request_context():
            assert safe_next_url("/profile?tab=stats") == "/profile?tab=stats"
            for unsafe in (None, "profile", "https://evil.test", "//evil.test/path"):
                assert safe_next_url(unsafe) == "/"

    def test_oauth_state_requires_equal_non_empty_values(self) -> None:
        assert validate_state("secret", "secret")
        assert not validate_state("secret", "wrong")
        assert not validate_state(None, None)

    def test_yandex_login_requires_configuration(self) -> None:
        self.app.config.update(
            YANDEX_CLIENT_ID=None, YANDEX_CLIENT_SECRET=None
        )
        response = self.client.get("/auth/yandex")
        assert response.status_code == 503

    def test_guest_remember_cookie_has_an_expiration(self) -> None:
        response = self.client.get("/")

        remember_cookie = next(
            header
            for header in response.headers.getlist("Set-Cookie")
            if header.startswith("remember_token=")
        )
        assert "Expires=" in remember_cookie
        assert "HttpOnly" in remember_cookie

    def test_yandex_login_builds_authorization_redirect_and_stores_state(self) -> None:
        self.app.config.update(
            YANDEX_CLIENT_ID="client-id",
            YANDEX_CLIENT_SECRET="client-secret",
            YANDEX_REDIRECT_URI="https://type.test/callback",
        )
        with patch("app.routes.auth.views.secrets.token_urlsafe", return_value="state-token"):
            response = self.client.get("/auth/yandex?next=/profile")
        query = parse_qs(urlsplit(response.location).query)
        assert response.status_code == 302
        assert query["client_id"] == ["client-id"]
        assert query["state"] == ["state-token"]
        assert query["redirect_uri"] == ["https://type.test/callback"]
        with self.client.session_transaction() as browser_session:
            assert browser_session["yandex_oauth_next"] == "/profile"

    def test_callback_rejects_bad_state_and_handles_provider_error(self) -> None:
        with self.client.session_transaction() as browser_session:
            browser_session["yandex_oauth_state"] = "expected"
        invalid = self.client.get("/auth/yandex/callback?state=wrong&code=abc")
        assert invalid.status_code == 400

        with self.client.session_transaction() as browser_session:
            browser_session["yandex_oauth_state"] = "expected"
        cancelled = self.client.get(
            "/auth/yandex/callback?state=expected&error=access_denied"
        )
        assert cancelled.status_code == 302
        assert cancelled.location.endswith("/auth")

    def test_authenticate_yandex_updates_guest_profile(self) -> None:
        user_id = self.current_user_id()
        token_response = Mock()
        token_response.raise_for_status.return_value = None
        token_response.json.return_value = {"access_token": "token"}
        profile_response = Mock()
        profile_response.raise_for_status.return_value = None
        profile_response.json.return_value = {
            "id": "ya-42",
            "login": " tester ",
            "first_name": "Иван",
            "last_name": "Иванов",
            "default_avatar_id": "avatar",
        }
        self.app.config.update(
            YANDEX_CLIENT_ID="client", YANDEX_CLIENT_SECRET="secret"
        )
        with self.app.test_request_context(), patch(
            "app.services.auth.requests.post", return_value=token_response
        ), patch("app.services.auth.requests.get", return_value=profile_response):
            from flask_login import login_user

            login_user(db.session.get(User, user_id))
            user = authenticate_yandex("code", "https://callback")
            assert user.id == user_id
            assert user.yandex_id == "ya-42"
            assert user.yandex_login == "tester"
            assert "avatar" in user.avatar_url

    def test_authenticate_yandex_wraps_invalid_provider_response(self) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {}
        self.app.config.update(
            YANDEX_CLIENT_ID="client", YANDEX_CLIENT_SECRET="secret"
        )
        with self.app.app_context(), patch(
            "app.services.auth.requests.post", return_value=response
        ):
            with pytest.raises(OAuthError):
                authenticate_yandex("code", "https://callback")

    def test_existing_yandex_account_absorbs_guest_actions(self) -> None:
        guest_id = self.current_user_id()
        with self.app.app_context():
            word = self.make_word()
            registered = self.make_user(yandex_id="ya-existing")
            registered_id = registered.id
            db.session.add(Action(
                user_id=guest_id,
                practice_item_id=word.id,
                action=Action.RIGHT_ANSWER,
            ))
            db.session.commit()

        self.app.config.update(
            YANDEX_CLIENT_ID="client", YANDEX_CLIENT_SECRET="secret"
        )
        token_response = Mock()
        token_response.raise_for_status.return_value = None
        token_response.json.return_value = {"access_token": "token"}
        profile_response = Mock()
        profile_response.raise_for_status.return_value = None
        profile_response.json.return_value = {"id": "ya-existing"}
        with self.app.test_request_context(), patch(
            "app.services.auth.requests.post", return_value=token_response
        ), patch("app.services.auth.requests.get", return_value=profile_response):
            from flask_login import login_user

            login_user(db.session.get(User, guest_id))
            authenticate_yandex("code", "https://callback")

        with self.app.app_context():
            assert db.session.get(User, guest_id) is None
            assert Action.query.one().user_id == registered_id
