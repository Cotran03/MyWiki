from sqlalchemy.exc import OperationalError

from mywiki import create_app


def test_app_factory_creates_independent_apps():
    first = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})
    second = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})

    assert first is not second
    assert first.testing is True
    assert first.config["MAIL_BACKEND"] == "console"


def test_health_endpoints(client):
    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.get_json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.get_json() == {"status": "ok"}


def test_landing_page_has_accessible_shell_and_bootstrap(client):
    response = client.get("/")
    html = response.get_data(as_text=True)
    logo = client.get("/static/img/MyWiki.png")

    assert response.status_code == 200
    assert '<html lang="ko"' in html
    assert "본문 바로가기" in html
    assert "bootstrap@5.3.8" in html
    assert "나만의 지식 공간" in html
    assert "static/img/MyWiki.png" in html
    assert 'rel="icon"' in html
    assert logo.status_code == 200
    assert logo.content_type == "image/png"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers


def test_friendly_404(client):
    response = client.get("/missing")

    assert response.status_code == 404
    assert "페이지를 찾을 수 없습니다" in response.get_data(as_text=True)


def test_database_operational_error_returns_503(app):
    @app.get("/_test/database-error")
    def database_error():
        raise OperationalError("SELECT 1", {}, OSError("database unavailable"))

    response = app.test_client().get("/_test/database-error")

    assert response.status_code == 503
    assert "데이터베이스 연결" in response.get_data(as_text=True)
