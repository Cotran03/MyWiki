from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from .extensions import db


def new_uuid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


document_tags = db.Table(
    "document_tags",
    db.Column(
        "document_id",
        db.String(36),
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "tag_id",
        db.String(36),
        db.ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    username = db.Column(db.String(32), nullable=False, unique=True, index=True)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    platform_role = db.Column(db.String(20), nullable=False, default="member")
    email_verified_at = db.Column(db.DateTime(timezone=True))
    disabled_at = db.Column(db.DateTime(timezone=True))

    wiki = db.relationship("Wiki", back_populates="owner", uselist=False)

    __table_args__ = (
        CheckConstraint(
            "platform_role IN ('member', 'admin')",
            name="valid_platform_role",
        ),
    )

    @property
    def is_active(self) -> bool:
        return self.disabled_at is None

    @property
    def is_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_admin(self) -> bool:
        return self.platform_role == "admin"


class Wiki(TimestampMixin, db.Model):
    __tablename__ = "wikis"

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    owner_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    name = db.Column(db.String(100), nullable=False)

    owner = db.relationship("User", back_populates="wiki")
    documents = db.relationship(
        "Document",
        back_populates="wiki",
        cascade="all, delete-orphan",
    )
    tags = db.relationship("Tag", back_populates="wiki", cascade="all, delete-orphan")


class Document(TimestampMixin, db.Model):
    __tablename__ = "documents"

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    wiki_id = db.Column(
        db.String(36),
        db.ForeignKey("wikis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title = db.Column(db.String(200), nullable=False)
    body_markdown = db.Column(db.Text, nullable=False, default="")
    current_revision_no = db.Column(db.Integer, nullable=False, default=1)
    trashed_at = db.Column(db.DateTime(timezone=True))
    purge_after = db.Column(db.DateTime(timezone=True))

    wiki = db.relationship("Wiki", back_populates="documents")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    revisions = db.relationship(
        "DocumentRevision",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentRevision.revision_no.desc()",
    )
    permissions = db.relationship(
        "DocumentPermission",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    tags = db.relationship("Tag", secondary=document_tags, back_populates="documents")

    __table_args__ = (
        CheckConstraint("current_revision_no >= 1", name="positive_revision"),
        CheckConstraint(
            "(trashed_at IS NULL AND purge_after IS NULL) OR "
            "(trashed_at IS NOT NULL AND purge_after IS NOT NULL)",
            name="valid_trash_dates",
        ),
        CheckConstraint(
            "purge_after IS NULL OR purge_after >= trashed_at",
            name="valid_purge_order",
        ),
        Index("ix_documents_wiki_updated", "wiki_id", "updated_at"),
        Index("ix_documents_purge_after", "purge_after"),
    )

    @property
    def owner_id(self) -> str:
        return self.wiki.owner_id

    @property
    def is_trashed(self) -> bool:
        return self.trashed_at is not None


class DocumentRevision(db.Model):
    __tablename__ = "document_revisions"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    document_id = db.Column(
        db.String(36),
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_no = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body_markdown = db.Column(db.Text, nullable=False, default="")
    edited_by_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    edit_summary = db.Column(db.String(300))
    operation = db.Column(db.String(20), nullable=False)
    restored_from_revision_id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        db.ForeignKey("document_revisions.id", ondelete="SET NULL"),
    )
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    document = db.relationship("Document", back_populates="revisions")
    edited_by = db.relationship("User", foreign_keys=[edited_by_id])
    restored_from = db.relationship("DocumentRevision", remote_side=[id])

    __table_args__ = (
        UniqueConstraint("document_id", "revision_no"),
        CheckConstraint("revision_no >= 1", name="positive_revision"),
        CheckConstraint(
            "operation IN ('create', 'edit', 'restore')",
            name="valid_operation",
        ),
        Index("ix_revisions_document_revision", "document_id", "revision_no"),
    )


class DocumentPermission(TimestampMixin, db.Model):
    __tablename__ = "document_permissions"

    document_id = db.Column(
        db.String(36),
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    grantee_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    access_level = db.Column(db.String(20), nullable=False)
    granted_by_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    document = db.relationship("Document", back_populates="permissions")
    grantee = db.relationship("User", foreign_keys=[grantee_id])
    granted_by = db.relationship("User", foreign_keys=[granted_by_id])

    __table_args__ = (
        CheckConstraint(
            "access_level IN ('viewer', 'editor')",
            name="valid_access_level",
        ),
        Index("ix_permissions_grantee_document", "grantee_id", "document_id"),
    )


class Tag(TimestampMixin, db.Model):
    __tablename__ = "tags"

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    wiki_id = db.Column(
        db.String(36),
        db.ForeignKey("wikis.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = db.Column(db.String(50), nullable=False)
    normalized_name = db.Column(db.String(50), nullable=False)

    wiki = db.relationship("Wiki", back_populates="tags")
    documents = db.relationship("Document", secondary=document_tags, back_populates="tags")

    __table_args__ = (UniqueConstraint("wiki_id", "normalized_name"),)


class Favorite(db.Model):
    __tablename__ = "favorites"

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id = db.Column(
        db.String(36),
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    user = db.relationship("User")
    document = db.relationship("Document")


class AuthToken(db.Model):
    __tablename__ = "auth_tokens"

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose = db.Column(db.String(30), nullable=False)
    token_digest = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    consumed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    user = db.relationship("User")

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('verify_email', 'reset_password')",
            name="valid_purpose",
        ),
    )


class AuditEvent(db.Model):
    __tablename__ = "audit_events"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    actor_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    action = db.Column(db.String(80), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.String(64))
    outcome = db.Column(db.String(20), nullable=False, default="success")
    request_id = db.Column(db.String(36))
    details = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    actor = db.relationship("User")

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('success', 'failure')",
            name="valid_outcome",
        ),
    )
