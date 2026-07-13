import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from ..extensions import db
from ..models import AuthToken, User, utcnow


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_token(user: User, purpose: str, ttl_seconds: int) -> str:
    now = utcnow()
    db.session.query(AuthToken).filter(
        AuthToken.user_id == user.id,
        AuthToken.purpose == purpose,
        AuthToken.consumed_at.is_(None),
    ).update({AuthToken.consumed_at: now}, synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    token = AuthToken(
        user_id=user.id,
        purpose=purpose,
        token_digest=_digest(raw_token),
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.session.add(token)
    db.session.commit()
    return raw_token


def find_valid_token(raw_token: str, purpose: str) -> AuthToken | None:
    token = db.session.scalar(
        db.select(AuthToken).where(
            AuthToken.token_digest == _digest(raw_token),
            AuthToken.purpose == purpose,
            AuthToken.consumed_at.is_(None),
        )
    )
    if token is None:
        return None

    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        return None
    return token


def consume_token(token: AuthToken) -> None:
    token.consumed_at = utcnow()
