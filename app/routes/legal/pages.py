from typing import cast

from flask import current_app, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user

from app.extensions import limiter
from app.models import User
from app.routes.legal import bp
from app.security.session import authenticate_browser_user
from app.services.auth import oauth_is_configured, safe_next_url
from app.services.legal import (
    PERSONAL_DATA_CONSENT_VERSION,
    PRIVACY_VERSION,
    TERMS_VERSION,
    has_current_legal_acceptance,
    record_legal_acceptance,
    revoke_legal_consent,
)


def _legal_context() -> dict[str, str]:
    return {
        "operator_name": current_app.config["LEGAL_OPERATOR_NAME"],
        "contact_email": current_app.config["LEGAL_CONTACT_EMAIL"],
        "service_url": current_app.config["URL"].rstrip("/"),
        "terms_version": TERMS_VERSION,
        "privacy_version": PRIVACY_VERSION,
        "personal_data_consent_version": PERSONAL_DATA_CONSENT_VERSION,
    }


@bp.get("/terms")
def terms():
    """Display the current terms of use."""
    return render_template("legal/terms.html", **_legal_context())


@bp.get("/privacy")
def privacy():
    """Display the current personal data processing policy."""
    return render_template("legal/privacy.html", **_legal_context())


@bp.get("/personal-data-consent")
def personal_data_consent():
    """Display the standalone personal data processing consent."""
    return render_template(
        "legal/personal_data_consent.html", **_legal_context()
    )


@bp.get("/consent")
def consent():
    """Display the mandatory first-use acceptance screen."""
    next_url = safe_next_url(request.args.get("next"))
    if current_user.is_authenticated and has_current_legal_acceptance(
        cast(User, current_user._get_current_object())
    ):
        return redirect(next_url)
    return render_template(
        "legal/consent.html",
        next_url=next_url,
        consent_revoked=request.args.get("revoked") == "1",
        oauth_configured=oauth_is_configured(),
        **_legal_context(),
    )


@bp.post("/consent")
@limiter.limit("10 per minute", override_defaults=False)
def accept_consent():
    """Record acceptance and continue as a guest or start Yandex OAuth."""
    next_url = safe_next_url(request.form.get("next"))
    flow = request.form.get("flow", "guest")
    if flow not in {"guest", "yandex"}:
        return "Unknown consent flow", 400
    if flow == "yandex" and not oauth_is_configured():
        return render_template(
            "legal/consent.html",
            next_url=next_url,
            oauth_configured=False,
            consent_error="Вход через Яндекс временно недоступен.",
            **_legal_context(),
        ), 503
    user = authenticate_browser_user()
    record_legal_acceptance(user)
    if flow == "yandex":
        return redirect(url_for("auth.yandex_login", next=next_url))
    return redirect(next_url)


@bp.get("/revoke")
@login_required
def revoke():
    """Display the consequences of withdrawing personal data consent."""
    return render_template(
        "legal/revoke.html",
        **_legal_context(),
    )


@bp.post("/revoke")
@limiter.limit(
    lambda: current_app.config["RATE_LIMIT_MUTATION"],
    override_defaults=False,
)
@login_required
def confirm_revoke():
    """Revoke consent, erase profile data, and terminate the session."""
    if request.form.get("confirm_revocation") != "accepted":
        return render_template(
            "legal/revoke.html",
            revoke_error="Подтвердите отзыв согласия и удаление данных.",
            **_legal_context(),
        ), 400

    user = cast(User, current_user._get_current_object())
    revoke_legal_consent(user)
    session.clear()
    logout_user()
    return redirect(url_for("legal.consent", revoked=1))
