from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException


def register_api_errors(app: Flask) -> None:
    """Return stable machine-readable payloads for generic API failures."""
    error_codes = {
        400: "bad_request",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
    }

    for status, code in error_codes.items():
        def handler(error: HTTPException, *, error_code: str = code):
            if not request.path.startswith("/api/"):
                return error.get_response()
            return jsonify({
                "error": error_code,
                "message": error.description,
            }), error.code

        app.register_error_handler(status, handler)
