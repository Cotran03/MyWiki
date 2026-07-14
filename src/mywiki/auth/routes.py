from collections.abc import Callable
from urllib.parse import urlsplit

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from ..extensions import db, limiter
from ..models import User, Wiki, utcnow
from ..services.audit import record_event
from ..services.mail import (
    MailDeliveryError,
    send_password_reset_message,
    send_verification_message,
)
from ..services.passwords import hash_password, needs_rehash, verify_password
from ..services.starter_documents import create_starter_documents
from ..services.tokens import consume_token, find_valid_token, issue_token
from . import bp
from .forms import EmailRequestForm, EmptyForm, LoginForm, RegisterForm, ResetPasswordForm


def _try_send_auth_message(
    sender: Callable[[User, str], None],
    user: User,
    raw_token: str,
    *,
    kind: str,
) -> bool:
    try:
        sender(user, raw_token)
    except MailDeliveryError:
        current_app.logger.exception(
            "Mail delivery failed | kind=%s user_id=%s",
            kind,
            user.id,
        )
        return False
    return True


def _safe_next(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.netloc or parsed.scheme or not value.startswith("/") or value.startswith("//"):
        return None
    return value


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        email = form.email.data.strip().lower()
        existing = db.session.scalar(
            db.select(User).where(or_(User.username == username, User.email == email))
        )
        if existing:
            flash("이미 사용 중인 사용자명 또는 이메일입니다.", "danger")
            return render_template("auth/register.html", form=form)

        user = User(
            username=username,
            email=email,
            display_name=form.display_name.data.strip(),
            password_hash=hash_password(form.password.data),
        )
        db.session.add(user)
        db.session.flush()
        wiki = Wiki(owner=user, name=f"{user.display_name}의 위키")
        db.session.add(wiki)
        record_event("auth.register", "user", user.id, actor_id=user.id)
        create_starter_documents(wiki, user)
        db.session.commit()

        raw_token = issue_token(
            user,
            "verify_email",
            current_app.config["AUTH_TOKEN_TTL_SECONDS"],
        )
        if not _try_send_auth_message(
            send_verification_message,
            user,
            raw_token,
            kind="verify_email",
        ):
            flash(
                "계정은 만들었지만 인증 메일 발송에 실패했습니다. "
                "SMTP 설정을 확인한 뒤 인증 메일을 다시 요청해 주세요.",
                "warning",
            )
            return redirect(url_for("auth.resend_verification"))
        flash("계정을 만들었습니다. 이메일 인증 링크를 확인해 주세요.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        identity = form.identity.data.strip().lower()
        user = db.session.scalar(
            db.select(User).where(or_(User.email == identity, User.username == identity))
        )
        if user is None or not verify_password(user.password_hash, form.password.data):
            record_event("auth.login", "user", user.id if user else None, outcome="failure")
            db.session.commit()
            flash("로그인 정보를 확인해 주세요.", "danger")
            return render_template("auth/login.html", form=form), 401
        if not user.is_active:
            flash("비활성화된 계정입니다.", "danger")
            return render_template("auth/login.html", form=form), 403
        if not user.is_verified:
            flash("로그인하려면 먼저 이메일 인증을 완료해 주세요.", "warning")
            return render_template("auth/login.html", form=form), 403

        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(form.password.data)
        record_event("auth.login", "user", user.id, actor_id=user.id)
        db.session.commit()
        login_user(user, remember=form.remember.data)
        return redirect(_safe_next(request.args.get("next")) or url_for("main.index"))

    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    form = EmptyForm()
    if form.validate_on_submit():
        record_event("auth.logout", "user", current_user.id)
        db.session.commit()
        logout_user()
    return redirect(url_for("main.index"))


@bp.get("/verify/<token>")
@limiter.limit("20 per minute")
def verify_email(token: str):
    auth_token = find_valid_token(token, "verify_email")
    if auth_token is None:
        flash("인증 링크가 유효하지 않거나 만료되었습니다.", "danger")
        return redirect(url_for("auth.resend_verification"))

    user = auth_token.user
    user.email_verified_at = user.email_verified_at or utcnow()
    consume_token(auth_token)
    record_event("auth.verify_email", "user", user.id, actor_id=user.id)
    db.session.commit()
    flash("이메일 인증을 완료했습니다. 이제 로그인할 수 있습니다.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/verify/resend", methods=["GET", "POST"])
@limiter.limit("3 per minute", methods=["POST"])
def resend_verification():
    form = EmailRequestForm()
    form.submit.label.text = "인증 메일 보내기"
    if form.validate_on_submit():
        user = db.session.scalar(
            db.select(User).where(User.email == form.email.data.strip().lower())
        )
        if user and user.is_active and not user.is_verified:
            raw_token = issue_token(
                user,
                "verify_email",
                current_app.config["AUTH_TOKEN_TTL_SECONDS"],
            )
            _try_send_auth_message(
                send_verification_message,
                user,
                raw_token,
                kind="verify_email",
            )
        flash("해당 계정이 있다면 인증 메일을 보냈습니다.", "info")
        return redirect(url_for("auth.login"))
    return render_template(
        "auth/email_request.html",
        form=form,
        heading="인증 메일 다시 받기",
    )


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per minute", methods=["POST"])
def forgot_password():
    form = EmailRequestForm()
    form.submit.label.text = "재설정 메일 보내기"
    if form.validate_on_submit():
        user = db.session.scalar(
            db.select(User).where(User.email == form.email.data.strip().lower())
        )
        if user and user.is_active and user.is_verified:
            raw_token = issue_token(
                user,
                "reset_password",
                current_app.config["RESET_TOKEN_TTL_SECONDS"],
            )
            _try_send_auth_message(
                send_password_reset_message,
                user,
                raw_token,
                kind="reset_password",
            )
        flash("해당 계정이 있다면 비밀번호 재설정 메일을 보냈습니다.", "info")
        return redirect(url_for("auth.login"))
    return render_template(
        "auth/email_request.html",
        form=form,
        heading="비밀번호 재설정",
    )


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def reset_password(token: str):
    auth_token = find_valid_token(token, "reset_password")
    if auth_token is None:
        flash("재설정 링크가 유효하지 않거나 만료되었습니다.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = auth_token.user
        user.password_hash = hash_password(form.password.data)
        consume_token(auth_token)
        record_event("auth.reset_password", "user", user.id, actor_id=user.id)
        db.session.commit()
        flash("비밀번호를 변경했습니다. 새 비밀번호로 로그인해 주세요.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)
