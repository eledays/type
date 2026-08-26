from app.extensions import db
from app.models import ErrorReport, PracticeItem, User


class InvalidReport(ValueError):
    """Ошибка проверки пользовательского сообщения."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def create_error_report(
    user: User,
    message: str,
    practice_item_id: int | None = None,
) -> ErrorReport:
    """Сохраняет сообщение об общей ошибке или ошибке в упражнении."""
    normalized_message = message.strip()
    if not normalized_message:
        raise InvalidReport("empty_message", "Опишите найденную ошибку")
    if len(normalized_message) > 2000:
        raise InvalidReport(
            "message_too_long",
            "Сообщение не должно быть длиннее 2000 символов",
        )
    if (
        practice_item_id is not None
        and db.session.get(PracticeItem, practice_item_id) is None
    ):
        raise InvalidReport(
            "item_not_found", "Practice item not found", 404
        )

    report = ErrorReport(
        user_id=user.id,
        practice_item_id=practice_item_id,
        message=normalized_message,
    )
    db.session.add(report)
    db.session.commit()
    return report
