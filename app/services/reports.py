from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import ErrorReport, PracticeItem, User


class InvalidReport(ValueError):
    """Ошибка проверки пользовательского сообщения."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def list_error_reports(
    status: str,
    *,
    page: int,
    page_size: int = 50,
) -> tuple[list[ErrorReport], int]:
    """Return one newest-first page of reports and the matching total."""
    conditions = []
    if status != "all":
        if status not in ErrorReport.STATUSES:
            raise InvalidReport("invalid_status", "Unknown report status")
        conditions.append(ErrorReport.status == status)
    total = int(db.session.scalar(
        select(func.count(ErrorReport.id)).where(*conditions)
    ) or 0)
    reports = list(db.session.scalars(
        select(ErrorReport)
        .options(
            joinedload(ErrorReport.user),
            joinedload(ErrorReport.practice_item),
        )
        .where(*conditions)
        .order_by(ErrorReport.created_at.desc(), ErrorReport.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).unique())
    return reports, total


def update_error_report(
    report_id: int,
    *,
    status: str,
    admin_note: str,
) -> ErrorReport | None:
    """Update workflow state and an internal administrator note."""
    if status not in ErrorReport.STATUSES:
        raise InvalidReport("invalid_status", "Unknown report status")
    normalized_note = admin_note.strip()
    if len(normalized_note) > 2000:
        raise InvalidReport(
            "admin_note_too_long",
            "Заметка не должна быть длиннее 2000 символов",
        )
    report = db.session.get(ErrorReport, report_id)
    if report is None:
        return None
    report.status = status
    report.admin_note = normalized_note or None
    db.session.commit()
    return report


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
