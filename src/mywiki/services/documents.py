from datetime import timedelta

from flask import current_app
from sqlalchemy import update

from ..extensions import db
from ..models import Document, DocumentRevision, Tag, User, Wiki, utcnow
from .audit import record_event


class RevisionConflictError(Exception):
    """Raised when a document changed after an edit form was opened."""


def create_document(
    wiki: Wiki,
    author: User,
    *,
    title: str,
    body_markdown: str,
    tags: str = "",
    summary: str = "",
    commit: bool = True,
) -> Document:
    document = Document(
        wiki=wiki,
        created_by=author,
        title=title.strip(),
        body_markdown=body_markdown,
        current_revision_no=1,
    )
    db.session.add(document)
    db.session.flush()
    db.session.add(
        DocumentRevision(
            document=document,
            revision_no=1,
            title=document.title,
            body_markdown=document.body_markdown,
            edited_by=author,
            edit_summary=summary.strip() or "문서 생성",
            operation="create",
        )
    )
    _sync_tags(document, tags)
    record_event("document.create", "document", document.id)
    if commit:
        db.session.commit()
    return document


def update_document(
    document: Document,
    editor: User,
    *,
    title: str,
    body_markdown: str,
    tags: str,
    summary: str,
    base_revision: int,
) -> Document:
    next_revision = base_revision + 1
    result = db.session.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.current_revision_no == base_revision,
            Document.trashed_at.is_(None),
        )
        .values(
            title=title.strip(),
            body_markdown=body_markdown,
            current_revision_no=next_revision,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:
        db.session.rollback()
        raise RevisionConflictError

    db.session.refresh(document)
    db.session.add(
        DocumentRevision(
            document_id=document.id,
            revision_no=next_revision,
            title=document.title,
            body_markdown=document.body_markdown,
            edited_by_id=editor.id,
            edit_summary=summary.strip() or "문서 수정",
            operation="edit",
        )
    )
    _sync_tags(document, tags)
    record_event(
        "document.edit",
        "document",
        document.id,
        details={"revision_no": next_revision},
    )
    db.session.commit()
    return document


def restore_revision(
    document: Document,
    revision: DocumentRevision,
    owner: User,
    *,
    base_revision: int,
) -> Document:
    next_revision = base_revision + 1
    result = db.session.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.current_revision_no == base_revision,
            Document.trashed_at.is_(None),
        )
        .values(
            title=revision.title,
            body_markdown=revision.body_markdown,
            current_revision_no=next_revision,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:
        db.session.rollback()
        raise RevisionConflictError

    db.session.refresh(document)
    db.session.add(
        DocumentRevision(
            document_id=document.id,
            revision_no=next_revision,
            title=document.title,
            body_markdown=document.body_markdown,
            edited_by_id=owner.id,
            edit_summary=f"revision {revision.revision_no} 복구",
            operation="restore",
            restored_from_revision_id=revision.id,
        )
    )
    record_event(
        "document.restore_revision",
        "document",
        document.id,
        details={"revision_no": next_revision, "restored_from": revision.revision_no},
    )
    db.session.commit()
    return document


def move_to_trash(document: Document) -> None:
    now = utcnow()
    document.trashed_at = now
    document.purge_after = now + timedelta(days=current_app.config["TRASH_RETENTION_DAYS"])
    record_event("document.trash", "document", document.id)
    db.session.commit()


def restore_from_trash(document: Document) -> None:
    document.trashed_at = None
    document.purge_after = None
    record_event("document.restore_trash", "document", document.id)
    db.session.commit()


def _sync_tags(document: Document, raw_tags: str) -> None:
    names: dict[str, str] = {}
    for value in raw_tags.split(","):
        name = value.strip()[:50]
        if name:
            names.setdefault(name.casefold(), name)

    document.tags.clear()
    for normalized_name, display_name in list(names.items())[:20]:
        tag = db.session.scalar(
            db.select(Tag).where(
                Tag.wiki_id == document.wiki_id,
                Tag.normalized_name == normalized_name,
            )
        )
        if tag is None:
            tag = Tag(
                wiki_id=document.wiki_id,
                name=display_name,
                normalized_name=normalized_name,
            )
            db.session.add(tag)
        document.tags.append(tag)
