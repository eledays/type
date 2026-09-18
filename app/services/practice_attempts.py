from typing import Any

from flask import current_app, session
from sqlalchemy import select

from app.extensions import db
from app.models import Action, PracticeItem, User
from app.services.practice_errors import PracticeError
from app.utils import add_action, get_anonymous_actions_remaining, get_cached_strike


def _get_typed_item(item_id: int, item_type: str) -> PracticeItem:
    """Load a practice item and verify the API type supplied by the client."""
    if item_type not in {"spelling", "paronym"}:
        raise PracticeError("invalid_card_type", "Invalid card type", 400)
    item = db.session.get(PracticeItem, item_id)
    if item is None or item.type != item_type:
        raise PracticeError("item_not_found", "Practice item not found", 404)
    return item


def check_answer(
    user: User,
    item_id: int,
    answer: str,
    item_type: str,
    request_id: str,
) -> dict[str, Any]:
    """Check an answer and persist its idempotent action."""
    anonymous_remaining = _ensure_quota(user, request_id=request_id)
    item = _get_typed_item(item_id, item_type)
    right_answer = item.get_correct_answer()
    blank = "_______" if item_type == "paronym" else "_"
    full_item = item.get_prompt().replace(blank, right_answer)
    correct = answer == right_answer
    explanation = item.explanation if item_type == "spelling" else None
    previous_strike = get_cached_strike(user.id)
    expected_action = (
        Action.RIGHT_ANSWER if correct else Action.WRONG_ANSWER
    )
    action_record, created = add_action(
        user_id=user.id,
        action=expected_action,
        practice_item_id=item_id,
        request_id=request_id,
    )
    if (
        action_record.practice_item_id != item_id
        or action_record.action != expected_action
    ):
        raise PracticeError(
            "idempotency_conflict",
            "Request id was already used for another action",
            409,
        )
    if created:
        session["strike"] = previous_strike + 1 if correct else 0
    return {
        "correct": correct,
        "full_word": full_item,
        "explanation": explanation,
        "strike": {
            "n": session.get("strike"),
            "levels": current_app.config["STRIKE_LEVELS"],
        },
        "anonymous_remaining": (
            None
            if anonymous_remaining is None
            else anonymous_remaining - int(created)
        ),
    }


def _can_skip_without_confirmation(
    user: User,
    item_id: int,
    recent_item_ids: list[int],
) -> bool:
    """Return whether skipping the card may reset the streak immediately."""
    grace_strike = int(current_app.config["PRACTICE_SWIPE_GRACE_STRIKE"])
    return (
        item_id in recent_item_ids
        or get_cached_strike(user.id) <= grace_strike
    )


def skip_card(
    user: User,
    item_id: int,
    item_type: str,
    *,
    confirmed: bool = False,
    request_id: str,
) -> tuple[int, int | None]:
    """Persist a card skip after applying quota and streak rules."""
    _get_typed_item(item_id, item_type)
    anonymous_remaining = _ensure_quota(user, request_id=request_id)
    recent_item_ids = _recent_item_ids(user.id)
    if not confirmed and not _can_skip_without_confirmation(
        user, item_id, recent_item_ids
    ):
        raise PracticeError(
            "strike_reset_confirmation_required",
            "Skipping this card will reset the strike",
            409,
        )
    if item_id in recent_item_ids:
        return get_cached_strike(user.id), anonymous_remaining
    session["strike"] = 0
    action_record, created = add_action(
        user_id=user.id,
        action=Action.SKIP,
        practice_item_id=item_id,
        request_id=request_id,
    )
    if (
        action_record.practice_item_id != item_id
        or action_record.action != Action.SKIP
    ):
        raise PracticeError(
            "idempotency_conflict",
            "Request id was already used for another action",
            409,
        )
    return 0, (
        None if anonymous_remaining is None
        else anonymous_remaining - int(created)
    )


def _recent_item_ids(user_id: int, limit: int = 3) -> list[int]:
    """Return recent card identifiers from newest to oldest."""
    return list(db.session.scalars(
        select(Action.practice_item_id)
        .where(Action.user_id == user_id)
        .order_by(Action.datetime.desc())
        .limit(limit)
    ))


def _ensure_quota(user: User, request_id: str) -> int | None:
    """Lock an anonymous user and return the quota remaining before action."""
    if user.is_anonymous_account:
        db.session.scalar(
            select(User.id).where(User.id == user.id).with_for_update()
        )
        db.session.refresh(user)
    remaining = get_anonymous_actions_remaining(user, lock=True)
    repeated_request = db.session.scalar(
        select(Action.id).where(
            Action.user_id == user.id,
            Action.request_id == request_id,
        )
    ) is not None
    if remaining == 0 and not repeated_request:
        raise PracticeError(
            "anonymous_limit_reached",
            "Войдите через Яндекс, чтобы продолжить.",
            403,
        )
    return remaining
