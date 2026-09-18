import json
import logging

from app.observability import JsonFormatter


def test_json_formatter_emits_machine_readable_context() -> None:
    record = logging.LogRecord(
        name="type",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.event = "request_completed"
    record.request_id = "request-42"
    record.status_code = 204

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "request_completed"
    assert payload["event"] == "request_completed"
    assert payload["request_id"] == "request-42"
    assert payload["status_code"] == 204
    assert payload["timestamp"].endswith("+00:00")
