from flask import jsonify, request

from app import create_app
from app.extensions import db


def test_trusted_apache_headers_define_public_request_metadata() -> None:
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "RATELIMIT_STORAGE_URI": "memory://",
        "TRUSTED_HOSTS": ["example.com"],
        "TRUSTED_PROXY_COUNT": 1,
        "WTF_CSRF_ENABLED": False,
    })

    @app.get("/proxy-metadata")
    def proxy_metadata():
        return jsonify({
            "host": request.host,
            "remote_addr": request.remote_addr,
            "scheme": request.scheme,
        })

    with app.app_context():
        db.create_all()

    response = app.test_client().get(
        "/proxy-metadata",
        base_url="http://10.0.0.20:8000",
        headers={
            "X-Forwarded-For": "198.51.100.25",
            "X-Forwarded-Host": "example.com",
            "X-Forwarded-Proto": "https",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "host": "example.com",
        "remote_addr": "198.51.100.25",
        "scheme": "https",
    }

    with app.app_context():
        db.session.remove()
        db.drop_all()
