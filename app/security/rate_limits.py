from flask import Flask, jsonify, request


def register_rate_limit_errors(app: Flask) -> None:
    """Регистрирует единый ответ при превышении частоты запросов."""

    @app.errorhandler(429)
    def rate_limit_exceeded(_error):
        message = "Too many requests. Please try again later."
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "rate_limit_exceeded",
                "message": message,
            }), 429
        return message, 429
