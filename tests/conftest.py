import pytest

from mywiki import create_app
from mywiki.extensions import db
from mywiki.models import DocumentPermission, User, Wiki, utcnow
from mywiki.services.documents import create_document
from mywiki.services.passwords import hash_password


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "test.db"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
            "MAIL_BACKEND": "console",
            "SERVER_NAME": "localhost",
        }
    )
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def create_user(username: str, *, verified: bool = True) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        display_name=username.title(),
        password_hash=hash_password("correct horse battery staple"),
        email_verified_at=utcnow() if verified else None,
    )
    db.session.add(user)
    db.session.flush()
    db.session.add(Wiki(owner=user, name=f"{username.title()}의 위키"))
    db.session.commit()
    return user


def create_test_document(owner: User, *, title: str = "비공개 문서", body: str = "본문"):
    return create_document(
        owner.wiki,
        owner,
        title=title,
        body_markdown=body,
        tags="테스트, 개인",
    )


def grant(document, owner: User, grantee: User, role: str) -> DocumentPermission:
    permission = DocumentPermission(
        document_id=document.id,
        grantee_id=grantee.id,
        granted_by_id=owner.id,
        access_level=role,
    )
    db.session.add(permission)
    db.session.commit()
    return permission


def login(client, username: str, password: str = "correct horse battery staple"):
    return client.post(
        "/auth/login",
        data={"identity": username, "password": password},
        follow_redirects=False,
    )


def logout(client):
    return client.post("/auth/logout", data={}, follow_redirects=False)
