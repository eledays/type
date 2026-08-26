from secrets import token_urlsafe

from flask import Flask, g, request


def _content_security_policy(nonce: str | None) -> str:
    script_sources = "script-src 'self'"
    if nonce is not None:
        script_sources += f" 'nonce-{nonce}'"
    return "; ".join((
        "default-src 'self'",
        script_sources,
        "style-src 'self' https://fonts.googleapis.com",
        "style-src-attr 'unsafe-inline'",
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

    @app.before_request
    def create_csp_nonce() -> None:
        g.csp_nonce = token_urlsafe(24)

    @app.context_processor
    def inject_csp_nonce() -> dict[str, str]:
        return {"csp_nonce": g.csp_nonce}

    @app.after_request
    def apply_security_headers(response):
        response.headers["Content-Security-Policy"] = _content_security_policy(
            getattr(g, "csp_nonce", None)
        )
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
