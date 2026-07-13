from mywiki import create_app


def test_app_factory_creates_independent_apps():
    first = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})
    second = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})

    assert first is not second
    assert first.testing is True


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

    assert response.status_code == 200
    assert '<html lang="ko"' in html
    assert "본문 바로가기" in html
    assert "bootstrap@5.3.8" in html
    assert "나만의 지식 공간" in html
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers


def test_friendly_404(client):
    response = client.get("/missing")

    assert response.status_code == 404
    assert "페이지를 찾을 수 없습니다" in response.get_data(as_text=True)
