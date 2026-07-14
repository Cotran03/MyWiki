from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from ..extensions import db, limiter
from ..models import Document, DocumentPermission, DocumentRevision, Tag, User
from ..services.audit import record_event
from ..services.authorization import (
    document_role,
    owned_documents_stmt,
    require_edit,
    require_owner,
    require_view,
    visible_documents_stmt,
)
from ..services.documents import (
    RevisionConflictError,
    create_document,
    move_to_trash,
    restore_from_trash,
    restore_revision,
    update_document,
)
from ..services.markdown import render_markdown
from . import bp
from .forms import DocumentForm, EmptyForm, ShareForm


def _document_or_404(owner_username: str, document_id: str) -> Document:
    document = db.session.get(Document, document_id)
    if document is None or document.wiki.owner.username != owner_username:
        abort(404)
    return document


def _document_url(document: Document) -> str:
    return url_for(
        "documents.detail",
        owner_username=document.wiki.owner.username,
        document_id=document.id,
    )


@bp.post("/documents/preview")
@login_required
@limiter.limit("60 per minute")
def preview():
    source = request.form.get("body_markdown", "")
    if len(source) > 1_000_000:
        abort(413)
    response = jsonify(html=str(render_markdown(source)))
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/documents/new", methods=["GET", "POST"])
@login_required
def create():
    form = DocumentForm()
    form.submit.label.text = "문서 만들기"
    if form.validate_on_submit():
        document = create_document(
            current_user.wiki,
            current_user,
            title=form.title.data,
            body_markdown=form.body_markdown.data or "",
            tags=form.tags.data or "",
            summary=form.edit_summary.data or "",
        )
        flash("문서를 만들었습니다.", "success")
        return redirect(_document_url(document))
    return render_template("documents/form.html", form=form, heading="새 문서")


@bp.get("/w/<owner_username>/docs/<document_id>")
@login_required
def detail(owner_username: str, document_id: str):
    document = _document_or_404(owner_username, document_id)
    role = require_view(current_user, document)
    return render_template(
        "documents/detail.html",
        document=document,
        rendered_body=render_markdown(document.body_markdown),
        role=role,
        delete_form=EmptyForm(),
    )


@bp.route("/w/<owner_username>/docs/<document_id>/edit", methods=["GET", "POST"])
@login_required
def edit(owner_username: str, document_id: str):
    document = _document_or_404(owner_username, document_id)
    require_edit(current_user, document)
    if document.is_trashed:
        abort(404)

    form = DocumentForm()
    if request.method == "GET":
        form.title.data = document.title
        form.body_markdown.data = document.body_markdown
        form.tags.data = ", ".join(tag.name for tag in document.tags)
        form.base_revision.data = str(document.current_revision_no)

    if form.validate_on_submit():
        try:
            base_revision = int(form.base_revision.data)
        except TypeError, ValueError:
            abort(409)
        try:
            update_document(
                document,
                current_user,
                title=form.title.data,
                body_markdown=form.body_markdown.data or "",
                tags=form.tags.data or "",
                summary=form.edit_summary.data or "",
                base_revision=base_revision,
            )
        except RevisionConflictError:
            abort(409)
        flash("문서를 저장했습니다.", "success")
        return redirect(_document_url(document))

    return render_template(
        "documents/form.html",
        form=form,
        heading=f"{document.title} 편집",
        document=document,
    )


@bp.post("/w/<owner_username>/docs/<document_id>/trash")
@login_required
def trash(owner_username: str, document_id: str):
    document = _document_or_404(owner_username, document_id)
    require_owner(current_user, document)
    form = EmptyForm()
    if form.validate_on_submit() and not document.is_trashed:
        move_to_trash(document)
        flash("문서를 휴지통으로 이동했습니다.", "success")
    return redirect(url_for("main.index"))


@bp.get("/trash")
@login_required
def trash_list():
    documents = db.session.scalars(
        owned_documents_stmt(current_user, trashed=True).order_by(Document.trashed_at.desc())
    ).all()
    return render_template("documents/trash.html", documents=documents, form=EmptyForm())


@bp.post("/w/<owner_username>/docs/<document_id>/restore")
@login_required
def restore_trash(owner_username: str, document_id: str):
    document = _document_or_404(owner_username, document_id)
    require_owner(current_user, document)
    form = EmptyForm()
    if form.validate_on_submit() and document.is_trashed:
        restore_from_trash(document)
        flash("문서를 복구했습니다.", "success")
    return redirect(_document_url(document))


@bp.get("/w/<owner_username>/docs/<document_id>/history")
@login_required
def history(owner_username: str, document_id: str):
    document = _document_or_404(owner_username, document_id)
    require_owner(current_user, document)
    revisions = db.session.scalars(
        db.select(DocumentRevision)
        .where(DocumentRevision.document_id == document.id)
        .order_by(DocumentRevision.revision_no.desc())
    ).all()
    return render_template(
        "documents/history.html",
        document=document,
        revisions=revisions,
    )


@bp.get("/w/<owner_username>/docs/<document_id>/history/<int:revision_no>")
@login_required
def revision_detail(owner_username: str, document_id: str, revision_no: int):
    document = _document_or_404(owner_username, document_id)
    require_owner(current_user, document)
    revision = db.session.scalar(
        db.select(DocumentRevision).where(
            DocumentRevision.document_id == document.id,
            DocumentRevision.revision_no == revision_no,
        )
    )
    if revision is None:
        abort(404)
    return render_template(
        "documents/revision.html",
        document=document,
        revision=revision,
        rendered_body=render_markdown(revision.body_markdown),
        form=EmptyForm(),
    )


@bp.post("/w/<owner_username>/docs/<document_id>/history/<int:revision_no>/restore")
@login_required
def restore_history(owner_username: str, document_id: str, revision_no: int):
    document = _document_or_404(owner_username, document_id)
    require_owner(current_user, document)
    revision = db.session.scalar(
        db.select(DocumentRevision).where(
            DocumentRevision.document_id == document.id,
            DocumentRevision.revision_no == revision_no,
        )
    )
    if revision is None:
        abort(404)
    form = EmptyForm()
    if form.validate_on_submit():
        try:
            restore_revision(
                document,
                revision,
                current_user,
                base_revision=document.current_revision_no,
            )
        except RevisionConflictError:
            abort(409)
        flash(f"revision {revision_no}을 새 revision으로 복구했습니다.", "success")
    return redirect(_document_url(document))


@bp.route("/w/<owner_username>/docs/<document_id>/share", methods=["GET", "POST"])
@login_required
def share(owner_username: str, document_id: str):
    document = _document_or_404(owner_username, document_id)
    require_owner(current_user, document)
    if document.is_trashed:
        abort(404)

    form = ShareForm()
    if form.validate_on_submit():
        target = db.session.scalar(
            db.select(User).where(User.username == form.username.data.strip().lower())
        )
        if target is None or not target.is_active or not target.is_verified:
            flash("공유할 수 있는 회원을 찾지 못했습니다.", "danger")
        elif target.id == current_user.id:
            flash("소유자 자신에게는 별도 권한을 줄 필요가 없습니다.", "warning")
        else:
            permission = db.session.get(DocumentPermission, (document.id, target.id))
            if permission is None:
                permission = DocumentPermission(
                    document_id=document.id,
                    grantee_id=target.id,
                    granted_by_id=current_user.id,
                    access_level=form.access_level.data,
                )
                db.session.add(permission)
            else:
                permission.access_level = form.access_level.data
                permission.granted_by_id = current_user.id
            record_event(
                "document.share",
                "document",
                document.id,
                details={"grantee_id": target.id, "access_level": form.access_level.data},
            )
            db.session.commit()
            flash("문서 공유 권한을 저장했습니다.", "success")
            return redirect(request.url)

    permissions = db.session.scalars(
        db.select(DocumentPermission)
        .where(DocumentPermission.document_id == document.id)
        .order_by(DocumentPermission.created_at)
    ).all()
    return render_template(
        "documents/share.html",
        document=document,
        form=form,
        permissions=permissions,
        revoke_form=EmptyForm(),
    )


@bp.post("/w/<owner_username>/docs/<document_id>/share/<grantee_id>/revoke")
@login_required
def revoke_share(owner_username: str, document_id: str, grantee_id: str):
    document = _document_or_404(owner_username, document_id)
    require_owner(current_user, document)
    form = EmptyForm()
    if form.validate_on_submit():
        permission = db.session.get(DocumentPermission, (document.id, grantee_id))
        if permission:
            db.session.delete(permission)
            record_event(
                "document.revoke_share",
                "document",
                document.id,
                details={"grantee_id": grantee_id},
            )
            db.session.commit()
            flash("공유 권한을 회수했습니다.", "success")
    return redirect(
        url_for("documents.share", owner_username=owner_username, document_id=document.id)
    )


@bp.get("/search")
@login_required
def search():
    query = request.args.get("q", "").strip()[:200]
    documents: list[Document] = []
    if query:
        pattern = f"%{query}%"
        stmt = (
            visible_documents_stmt(current_user)
            .outerjoin(Document.tags)
            .where(
                or_(
                    Document.title.ilike(pattern),
                    Document.body_markdown.ilike(pattern),
                    Tag.name.ilike(pattern),
                )
            )
            .order_by(Document.updated_at.desc())
        )
        documents = db.session.scalars(stmt).unique().all()
    roles = {document.id: document_role(current_user, document) for document in documents}
    return render_template(
        "documents/search.html",
        query=query,
        documents=documents,
        roles=roles,
    )
