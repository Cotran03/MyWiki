from mywiki.extensions import db
from mywiki.models import Document, DocumentPermission, DocumentRevision

from .conftest import create_test_document, create_user, grant, login, logout


def detail_url(document):
    return f"/w/{document.wiki.owner.username}/docs/{document.id}"


def test_unrelated_member_cannot_discover_document(app, client):
    with app.app_context():
        alice = create_user("alice")
        create_user("bob")
        document = create_test_document(alice, title="앨리스의 비밀")
        url = detail_url(document)

    login(client, "bob")
    assert client.get(url).status_code == 404
    search = client.get("/search?q=앨리스의+비밀")
    assert search.status_code == 200
    assert url not in search.get_data(as_text=True)


def test_viewer_can_read_but_cannot_edit(app, client):
    with app.app_context():
        alice = create_user("alice")
        bob = create_user("bob")
        document = create_test_document(alice)
        grant(document, alice, bob, "viewer")
        url = detail_url(document)

    login(client, "bob")
    assert client.get(url).status_code == 200
    assert client.get(f"{url}/edit").status_code == 403
    assert client.get(f"{url}/history").status_code == 403


def test_editor_can_edit_but_cannot_share_or_delete(app, client):
    with app.app_context():
        alice = create_user("alice")
        bob = create_user("bob")
        document = create_test_document(alice)
        grant(document, alice, bob, "editor")
        document_id = document.id
        url = detail_url(document)

    login(client, "bob")
    response = client.post(
        f"{url}/edit",
        data={
            "title": "편집된 문서",
            "body_markdown": "Bob이 편집함",
            "tags": "공유",
            "edit_summary": "공유 편집",
            "base_revision": "1",
        },
    )
    assert response.status_code == 302
    assert client.get(f"{url}/share").status_code == 403
    assert client.post(f"{url}/trash", data={}).status_code == 403

    with app.app_context():
        updated = db.session.get(Document, document_id)
        assert updated.title == "편집된 문서"
        assert updated.current_revision_no == 2
        assert (
            db.session.scalar(
                db.select(DocumentRevision).where(
                    DocumentRevision.document_id == document_id,
                    DocumentRevision.revision_no == 2,
                )
            ).edited_by.username
            == "bob"
        )


def test_revoking_share_immediately_hides_document(app, client):
    with app.app_context():
        alice = create_user("alice")
        bob = create_user("bob")
        document = create_test_document(alice)
        grant(document, alice, bob, "viewer")
        bob_id = bob.id
        document_id = document.id
        url = detail_url(document)

    login(client, "bob")
    assert client.get(url).status_code == 200
    logout(client)
    login(client, "alice")
    response = client.post(f"{url}/share/{bob_id}/revoke", data={})
    assert response.status_code == 302
    logout(client)
    login(client, "bob")
    assert client.get(url).status_code == 404

    with app.app_context():
        assert db.session.get(DocumentPermission, (document_id, bob_id)) is None


def test_stale_edit_returns_conflict_without_overwrite(app, client):
    with app.app_context():
        alice = create_user("alice")
        document = create_test_document(alice)
        document_id = document.id
        url = detail_url(document)

    login(client, "alice")
    first = client.post(
        f"{url}/edit",
        data={
            "title": "첫 저장",
            "body_markdown": "최신 본문",
            "tags": "",
            "edit_summary": "",
            "base_revision": "1",
        },
    )
    stale = client.post(
        f"{url}/edit",
        data={
            "title": "뒤늦은 저장",
            "body_markdown": "덮어쓰면 안 됨",
            "tags": "",
            "edit_summary": "",
            "base_revision": "1",
        },
    )

    assert first.status_code == 302
    assert stale.status_code == 409
    with app.app_context():
        document = db.session.get(Document, document_id)
        assert document.title == "첫 저장"
        assert document.current_revision_no == 2


def test_owner_can_restore_old_revision_as_new_revision(app, client):
    with app.app_context():
        alice = create_user("alice")
        document = create_test_document(alice, title="원래 제목", body="원래 본문")
        document_id = document.id
        url = detail_url(document)

    login(client, "alice")
    client.post(
        f"{url}/edit",
        data={
            "title": "바뀐 제목",
            "body_markdown": "바뀐 본문",
            "tags": "",
            "edit_summary": "변경",
            "base_revision": "1",
        },
    )
    response = client.post(f"{url}/history/1/restore", data={})

    assert response.status_code == 302
    with app.app_context():
        restored = db.session.get(Document, document_id)
        assert restored.title == "원래 제목"
        assert restored.body_markdown == "원래 본문"
        assert restored.current_revision_no == 3
        revision = db.session.scalar(
            db.select(DocumentRevision).where(
                DocumentRevision.document_id == document_id,
                DocumentRevision.revision_no == 3,
            )
        )
        assert revision.operation == "restore"
        assert revision.restored_from_revision_id is not None


def test_trash_hides_document_from_shared_user_and_search(app, client):
    with app.app_context():
        alice = create_user("alice")
        bob = create_user("bob")
        document = create_test_document(alice, title="사라질 문서")
        grant(document, alice, bob, "viewer")
        url = detail_url(document)

    login(client, "alice")
    assert client.post(f"{url}/trash", data={}).status_code == 302
    logout(client)
    login(client, "bob")
    assert client.get(url).status_code == 404
    assert "사라질 문서" not in client.get("/search?q=사라질").get_data(as_text=True)
