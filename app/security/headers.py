from flask import Flask, request


CONTENT_SECURITY_POLICY = "; ".join((
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://avatars.yandex.net",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
))


def register_security_headers(app: Flask) -> None:
    """Добавляет браузерные политики и запрещает кэш приватных ответов."""

    @app.after_request
    def apply_security_headers(response):
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        if app.config.get("HSTS_ENABLED", False):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        versioned_static = (
            request.endpoint == "static"
            and (
                request.path.startswith("/static/img/backs/")
                or request.args.get("v")
            )
        )
        if not versioned_static:
            response.headers.setdefault("Cache-Control", "private, no-store")
            response.headers.setdefault("Pragma", "no-cache")
        return response
