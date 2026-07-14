import pytest

from mywiki.extensions import db
from mywiki.models import AuthToken, Document, DocumentRevision, User, Wiki
from mywiki.services.mail import MailDeliveryError

from .conftest import create_user, login


def test_registration_creates_unverified_user_wiki_and_token(app, client):
    response = client.post(
        "/auth/register",
        data={
            "username": "new_user",
            "display_name": "새 사용자",
            "email": "new_user@example.com",
            "password": "long and unique password",
            "password_confirm": "long and unique password",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.username == "new_user"))
        assert user is not None
        assert user.is_verified is False
        wiki = db.session.scalar(db.select(Wiki).where(Wiki.owner_id == user.id))
        assert wiki is not None
        documents = list(
            db.session.scalars(
                db.select(Document).where(Document.wiki_id == wiki.id).order_by(Document.title)
            )
        )
        assert {document.title for document in documents} == {
            "Markdown 사용법",
            "MyWiki 사용법",
        }
        assert all(document.current_revision_no == 1 for document in documents)
        assert all(document.created_by_id == user.id for document in documents)
        assert (
            db.session.scalar(
                db.select(db.func.count(DocumentRevision.id)).where(
                    DocumentRevision.document_id.in_([document.id for document in documents])
                )
            )
            == 2
        )
        assert "미리보기" in next(
            document.body_markdown for document in documents if document.title == "MyWiki 사용법"
        )
        assert "CommonMark" in next(
            document.body_markdown for document in documents if document.title == "Markdown 사용법"
        )
        token = db.session.scalar(db.select(AuthToken).where(AuthToken.user_id == user.id))
        assert token is not None
        assert token.token_digest != ""


def test_registration_survives_mail_delivery_failure(app, client, monkeypatch):
    def fail_delivery(user, raw_token):
        raise MailDeliveryError("temporary failure")

    monkeypatch.setattr(
        "mywiki.auth.routes.send_verification_message",
        fail_delivery,
    )

    response = client.post(
        "/auth/register",
        data={
            "username": "mail_failure",
            "display_name": "메일 실패",
            "email": "mail_failure@example.com",
            "password": "long and unique password",
            "password_confirm": "long and unique password",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "계정은 만들었지만 인증 메일 발송에 실패했습니다" in response.get_data(as_text=True)
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.username == "mail_failure"))
        assert user is not None


def test_registration_rolls_back_if_starter_document_creation_fails(app, client, monkeypatch):
    def fail_starter_document_creation(wiki, owner):
        raise RuntimeError("starter document creation failed")

    monkeypatch.setattr(
        "mywiki.auth.routes.create_starter_documents",
        fail_starter_document_creation,
    )

    with pytest.raises(RuntimeError, match="starter document creation failed"):
        client.post(
            "/auth/register",
            data={
                "username": "rolled_back",
                "display_name": "롤백 확인",
                "email": "rolled_back@example.com",
                "password": "long and unique password",
                "password_confirm": "long and unique password",
            },
        )

    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.username == "rolled_back"))
        assert user is None


def test_unverified_user_cannot_login(app, client):
    with app.app_context():
        create_user("alice", verified=False)

    response = login(client, "alice")

    assert response.status_code == 403
    assert "이메일 인증" in response.get_data(as_text=True)


def test_verified_user_can_login_and_logout(app, client):
    with app.app_context():
        create_user("alice")

    response = login(client, "alice")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Alice의 위키" in dashboard.get_data(as_text=True)

    response = client.post("/auth/logout", data={})
    assert response.status_code == 302


def test_login_rejects_open_redirect(app, client):
    with app.app_context():
        create_user("alice")

    response = client.post(
        "/auth/login?next=//evil.example/path",
        data={
            "identity": "alice",
            "password": "correct horse battery staple",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
