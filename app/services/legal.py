from __future__ import annotations

from flask import current_app
from sqlalchemy import delete

from app.extensions import db
from app.models import (
    Action,
    ErrorReport,
    LegalAcceptance,
    PracticeProgress,
    Settings,
    User,
    UserPracticeStats,
)
from app.time_utils import utc_now


TERMS_VERSION = "2026-09-07"
PRIVACY_VERSION = "2026-09-07"
PERSONAL_DATA_CONSENT_VERSION = "2026-09-07"


def has_current_legal_acceptance(user: User) -> bool:
    """Return whether the user accepted every currently published document."""
    if not current_app.config.get("LEGAL_CONSENT_REQUIRED", True):
        return True
    return LegalAcceptance.query.filter_by(
        user_id=user.id,
        terms_version=TERMS_VERSION,
        privacy_version=PRIVACY_VERSION,
        personal_data_consent_version=PERSONAL_DATA_CONSENT_VERSION,
        revoked_at=None,
    ).first() is not None


def create_anonymous_user() -> User:
    """Create the local profile needed after an explicit acceptance."""
    user = User(settings=Settings())
    db.session.add(user)
    db.session.flush()
    return user


def record_legal_acceptance(user: User) -> LegalAcceptance:
    """Persist acceptance of the complete current document set once."""
    existing = LegalAcceptance.query.filter_by(
        user_id=user.id,
        terms_version=TERMS_VERSION,
        privacy_version=PRIVACY_VERSION,
        personal_data_consent_version=PERSONAL_DATA_CONSENT_VERSION,
        revoked_at=None,
    ).first()
    if existing is not None:
        return existing
    acceptance = LegalAcceptance(
        user=user,
        terms_version=TERMS_VERSION,
        privacy_version=PRIVACY_VERSION,
        personal_data_consent_version=PERSONAL_DATA_CONSENT_VERSION,
    )
    db.session.add(acceptance)
    db.session.commit()
    return acceptance


def revoke_legal_consent(user: User) -> None:
    """Revoke active consent and erase data no longer needed for legal proof."""
    revoked_at = utc_now()
    for acceptance in LegalAcceptance.query.filter_by(
        user_id=user.id, revoked_at=None
    ):
        acceptance.revoked_at = revoked_at

    for model in (Action, ErrorReport, PracticeProgress, UserPracticeStats):
        db.session.execute(delete(model).where(model.user_id == user.id))

    user.settings = None
    user.telegram_id = None
    user.yandex_id = None
    user.yandex_login = None
    user.first_name = None
    user.last_name = None
    user.avatar_url = None
    user.identified_at = None
    user.is_admin = False
    db.session.commit()
