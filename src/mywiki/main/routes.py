from flask import jsonify, render_template
from flask_login import current_user
from sqlalchemy import text

from ..extensions import db
from ..models import Document, DocumentPermission
from ..services.authorization import visible_documents_stmt
from . import bp


@bp.get("/")
def index():
    if not current_user.is_authenticated:
        return render_template("main/landing.html")

    documents = db.session.scalars(
        visible_documents_stmt(current_user).order_by(Document.updated_at.desc()).limit(20)
    ).all()
    shared_roles = {
        permission.document_id: permission.access_level
        for permission in db.session.scalars(
            db.select(DocumentPermission).where(DocumentPermission.grantee_id == current_user.id)
        ).all()
    }
    return render_template(
        "main/dashboard.html",
        documents=documents,
        shared_roles=shared_roles,
    )


@bp.get("/health/live")
def health_live():
    return jsonify(status="ok")


@bp.get("/health/ready")
def health_ready():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok")
