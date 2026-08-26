from tests.base import AppTestCase


class TestSecurityHeaders(AppTestCase):
    def test_dynamic_responses_use_security_headers_and_no_store(self) -> None:
        response = self.client.get("/")

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == (
            "strict-origin-when-cross-origin"
        )
        assert response.headers["Permissions-Policy"] == (
            "camera=(), microphone=(), geolocation=()"
        )
        assert "frame-ancestors 'none'" in response.headers[
            "Content-Security-Policy"
        ]
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["Pragma"] == "no-cache"
        assert "max-age=31536000" in response.headers[
            "Strict-Transport-Security"
        ]

    def test_authentication_cookies_are_explicitly_hardened(self) -> None:
        response = self.client.get("/")
        cookies = response.headers.getlist("Set-Cookie")

        assert cookies
        for cookie in cookies:
            assert "Secure" in cookie
            assert "HttpOnly" in cookie
            assert "SameSite=Lax" in cookie

    def test_versioned_static_assets_remain_publicly_cacheable(self) -> None:
        response = self.client.get("/static/img/backs/dark/0.webp?v=test")

        assert response.headers["Cache-Control"] == (
            "public, max-age=31536000, immutable"
        )
