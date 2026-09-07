from tests.base import AppTestCase

from app.extensions import db
from app.models import Action, LegalAcceptance, User, UserPracticeStats
from app.services.legal import (
    PERSONAL_DATA_CONSENT_VERSION,
    PRIVACY_VERSION,
    TERMS_VERSION,
)


class TestLegalConsent(AppTestCase):
    legal_consent_required = True

    def test_documents_are_public_and_do_not_create_profile(self) -> None:
        self.app.config["URL"] = "https://type.example.test/"
        for url, heading in (
            ("/legal/terms", "Условия использования сервиса type"),
            ("/legal/privacy", "Политика обработки персональных данных"),
            ("/legal/personal-data-consent", "Согласие на обработку"),
        ):
            response = self.client.get(url)
            assert response.status_code == 200
            assert heading.encode() in response.data
            assert b'href="https://type.example.test"' in response.data

        with self.app.app_context():
            assert User.query.count() == 0

    def test_application_is_blocked_without_creating_profile(self) -> None:
        page = self.client.get("/?task=5")
        api = self.client.get("/api/v1/practice/cards")

        assert page.status_code == 302
        assert page.location == "/legal/consent?next=/?task%3D5"
        assert api.status_code == 403
        assert api.get_json()["error"] == "legal_consent_required"
        with self.app.app_context():
            assert User.query.count() == 0

    def test_consent_page_offers_yandex_and_guest_with_document_links(self) -> None:
        self.app.config.update(
            YANDEX_CLIENT_ID="client-id",
            YANDEX_CLIENT_SECRET="client-secret",
        )
        response = self.client.get("/legal/consent")

        assert response.status_code == 200
        assert "Войти через Яндекс".encode() in response.data
        assert "Попробовать без регистрации".encode() in response.data
        assert ">Начать</button>".encode() not in response.data
        assert b'type="checkbox"' not in response.data
        assert b'class="consent-preview"' in response.data
        assert b'class="consent-dimmer"' in response.data
        assert b'href="/legal/terms"' in response.data
        assert b'href="/legal/privacy"' in response.data
        assert b'href="/legal/personal-data-consent"' in response.data
        assert (
            "Листай — готовься к ЕГЭ по русскому"
            .encode() in response.data
        )

        accepted = self.client.post(
            "/legal/consent", data={"flow": "guest"}
        )
        assert accepted.status_code == 302
        with self.app.app_context():
            assert LegalAcceptance.query.count() == 1

    def test_yandex_choice_starts_oauth_without_auth_page(self) -> None:
        self.app.config.update(
            YANDEX_CLIENT_ID="client-id",
            YANDEX_CLIENT_SECRET="client-secret",
        )

        accepted = self.client.post(
            "/legal/consent",
            data={"flow": "yandex", "next": "/profile"},
        )

        assert accepted.status_code == 302
        assert accepted.location == "/auth/yandex?next=/profile"
        oauth = self.client.get(accepted.location)
        assert oauth.status_code == 302
        assert oauth.location.startswith("https://oauth.yandex.ru/authorize?")

    def test_acceptance_records_versions_and_unlocks_requested_page(self) -> None:
        response = self.client.post(
            "/legal/consent",
            data={
                "terms": "accepted",
                "privacy": "accepted",
                "personal_data": "accepted",
                "next": "/profile",
            },
        )

        assert response.status_code == 302
        assert response.location == "/profile"
        assert self.client.get("/profile").status_code == 200
        with self.app.app_context():
            acceptance = LegalAcceptance.query.one()
            assert acceptance.terms_version == TERMS_VERSION
            assert acceptance.privacy_version == PRIVACY_VERSION
            assert (
                acceptance.personal_data_consent_version
                == PERSONAL_DATA_CONSENT_VERSION
            )
            assert acceptance.accepted_at is not None

    def test_existing_profile_must_accept_current_versions(self) -> None:
        with self.app.app_context():
            user = self.make_user(yandex_id="existing-user")
            user_id = user.id
        with self.client.session_transaction() as browser_session:
            browser_session["_user_id"] = str(user_id)
            browser_session["_fresh"] = True

        assert self.client.get("/").status_code == 302
        accepted = self.client.post(
            "/legal/consent",
            data={
                "terms": "accepted",
                "privacy": "accepted",
                "personal_data": "accepted",
            },
        )
        assert accepted.status_code == 302
        assert self.client.get("/").status_code == 200

    def test_next_url_cannot_redirect_off_site(self) -> None:
        response = self.client.post(
            "/legal/consent",
            data={
                "terms": "accepted",
                "privacy": "accepted",
                "personal_data": "accepted",
                "next": "https://evil.test/path",
            },
        )

        assert response.location == "/"

    def test_revocation_requires_explicit_confirmation(self) -> None:
        self.client.post(
            "/legal/consent",
            data={
                "terms": "accepted",
                "privacy": "accepted",
                "personal_data": "accepted",
            },
        )

        response = self.client.post("/legal/revoke")

        assert response.status_code == 400
        assert "Подтвердите отзыв".encode() in response.data
        with self.app.app_context():
            assert LegalAcceptance.query.one().revoked_at is None

    def test_revocation_erases_profile_data_and_blocks_access(self) -> None:
        self.client.post(
            "/legal/consent",
            data={
                "terms": "accepted",
                "privacy": "accepted",
                "personal_data": "accepted",
            },
        )
        with self.client.session_transaction() as browser_session:
            user_id = int(browser_session["_user_id"])
        with self.app.app_context():
            user = db.session.get(User, user_id)
            word = self.make_word()
            user.yandex_id = "revoked-yandex-id"
            user.first_name = "Иван"
            db.session.add(Action(
                user_id=user_id,
                practice_item_id=word.id,
                action=Action.RIGHT_ANSWER,
            ))
            db.session.commit()

        response = self.client.post(
            "/legal/revoke",
            data={"confirm_revocation": "accepted"},
        )

        assert response.status_code == 302
        assert response.location == "/legal/consent?revoked=1"
        assert self.client.get("/").status_code == 302
        with self.app.app_context():
            user = db.session.get(User, user_id)
            assert user is not None
            assert user.yandex_id is None
            assert user.first_name is None
            assert user.settings is None
            assert Action.query.filter_by(user_id=user_id).count() == 0
            assert db.session.get(UserPracticeStats, user_id) is None
            acceptance = LegalAcceptance.query.filter_by(
                user_id=user_id
            ).one()
            assert acceptance.revoked_at is not None
