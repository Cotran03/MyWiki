from flask import g, has_request_context
from flask_login import current_user

from ..extensions import db
from ..models import AuditEvent


def record_event(
    action: str,
    target_type: str,
    target_id: str | None = None,
    *,
    outcome: str = "success",
    details: dict | None = None,
    actor_id: str | None = None,
) -> AuditEvent:
    if actor_id is None and has_request_context() and current_user.is_authenticated:
        actor_id = current_user.id

    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        request_id=g.get("request_id") if has_request_context() else None,
        details=details or {},
    )
    db.session.add(event)
    return event
