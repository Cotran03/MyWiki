from __future__ import annotations

from flask import abort
from sqlalchemy import and_, or_, select

from ..extensions import db
from ..models import Document, DocumentPermission, User, Wiki

ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}


def document_role(user: User, document: Document) -> str | None:
    if not user.is_authenticated or not user.is_active:
        return None
    if document.wiki.owner_id == user.id:
        return "owner"
    if document.is_trashed:
        return None

    permission = db.session.get(DocumentPermission, (document.id, user.id))
    return permission.access_level if permission else None


def can_view(user: User, document: Document) -> bool:
    return document_role(user, document) is not None


def can_edit(user: User, document: Document) -> bool:
    role = document_role(user, document)
    return role is not None and ROLE_RANK[role] >= ROLE_RANK["editor"]


def is_owner(user: User, document: Document) -> bool:
    return document_role(user, document) == "owner"


def require_view(user: User, document: Document) -> str:
    role = document_role(user, document)
    if role is None:
        abort(404)
    return role


def require_edit(user: User, document: Document) -> str:
    role = require_view(user, document)
    if ROLE_RANK[role] < ROLE_RANK["editor"]:
        abort(403)
    return role


def require_owner(user: User, document: Document) -> str:
    role = require_view(user, document)
    if role != "owner":
        abort(403)
    return role


def visible_documents_stmt(user: User, *, include_trashed: bool = False):
    permission_match = and_(
        DocumentPermission.document_id == Document.id,
        DocumentPermission.grantee_id == user.id,
    )
    stmt = (
        select(Document)
        .join(Wiki, Document.wiki_id == Wiki.id)
        .outerjoin(DocumentPermission, permission_match)
        .where(or_(Wiki.owner_id == user.id, DocumentPermission.grantee_id == user.id))
        .distinct()
    )
    if not include_trashed:
        stmt = stmt.where(Document.trashed_at.is_(None))
    return stmt


def owned_documents_stmt(user: User, *, trashed: bool = False):
    stmt = select(Document).join(Wiki).where(Wiki.owner_id == user.id)
    if trashed:
        return stmt.where(Document.trashed_at.is_not(None))
    return stmt.where(Document.trashed_at.is_(None))
