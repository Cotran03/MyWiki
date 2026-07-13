import smtplib
import ssl
from datetime import UTC, datetime
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

from flask import current_app, render_template, url_for

from ..models import User


class MailDeliveryError(RuntimeError):
    """Raised when the configured provider cannot accept a message."""


def send_verification_message(user: User, raw_token: str) -> None:
    verification_url = _action_url("auth.verify_email", token=raw_token)
    _deliver(
        "이메일 인증",
        recipient=user.email,
        display_name=user.display_name,
        action_url=verification_url,
        action_label="이메일 인증하기",
        explanation="MyWiki 가입을 완료하려면 아래 버튼을 눌러 이메일 주소를 인증해 주세요.",
        user_id=user.id,
    )


def send_password_reset_message(user: User, raw_token: str) -> None:
    reset_url = _action_url("auth.reset_password", token=raw_token)
    _deliver(
        "비밀번호 재설정",
        recipient=user.email,
        display_name=user.display_name,
        action_url=reset_url,
        action_label="비밀번호 재설정하기",
        explanation="MyWiki 비밀번호를 다시 설정하려면 아래 버튼을 눌러 주세요.",
        user_id=user.id,
    )


def send_test_message(recipient: str) -> None:
    _deliver(
        "SMTP 연결 테스트",
        recipient=recipient,
        display_name="MyWiki 사용자",
        action_url=current_app.config["BASE_URL"],
        action_label="MyWiki 열기",
        explanation="MyWiki SMTP 설정이 정상적으로 동작하고 있습니다.",
    )


def _action_url(endpoint: str, **values: str) -> str:
    path = url_for(endpoint, _external=False, **values)
    return f"{current_app.config['BASE_URL']}{path}"


def _deliver(
    subject: str,
    *,
    recipient: str,
    display_name: str,
    action_url: str,
    action_label: str,
    explanation: str,
    user_id: str | None = None,
) -> None:
    backend = current_app.config["MAIL_BACKEND"]
    if backend == "console":
        current_app.logger.warning(
            "DEV MAIL | subject=%s user_id=%s url=%s",
            subject,
            user_id or "test",
            action_url,
        )
        return
    if backend != "smtp":
        raise RuntimeError(f"Unsupported MAIL_BACKEND: {backend}")

    message = _build_message(
        subject,
        recipient=recipient,
        display_name=display_name,
        action_url=action_url,
        action_label=action_label,
        explanation=explanation,
    )
    _send_smtp(message)
    current_app.logger.info("Mail sent | subject=%s user_id=%s", subject, user_id or "test")


def _build_message(
    subject: str,
    *,
    recipient: str,
    display_name: str,
    action_url: str,
    action_label: str,
    explanation: str,
) -> EmailMessage:
    message = EmailMessage()
    prefix = current_app.config["MAIL_SUBJECT_PREFIX"].strip()
    message["Subject"] = f"{prefix} {subject}" if prefix else subject
    message["From"] = Address(
        display_name=current_app.config["MAIL_FROM_NAME"],
        addr_spec=current_app.config["MAIL_DEFAULT_SENDER"],
    )
    message["To"] = recipient
    message["Date"] = format_datetime(datetime.now(UTC))
    message["Message-ID"] = make_msgid()

    context = {
        "display_name": display_name,
        "explanation": explanation,
        "action_url": action_url,
        "action_label": action_label,
    }
    message.set_content(render_template("emails/action.txt", **context))
    message.add_alternative(render_template("emails/action.html", **context), subtype="html")
    return message


def _send_smtp(message: EmailMessage) -> None:
    context = ssl.create_default_context()
    server = current_app.config["MAIL_SERVER"]
    port = current_app.config["MAIL_PORT"]
    timeout = current_app.config["MAIL_TIMEOUT_SECONDS"]

    try:
        if current_app.config["MAIL_USE_SSL"]:
            client = smtplib.SMTP_SSL(
                host=server,
                port=port,
                timeout=timeout,
                context=context,
            )
        else:
            client = smtplib.SMTP(host=server, port=port, timeout=timeout)

        with client:
            client.ehlo()
            if current_app.config["MAIL_USE_TLS"]:
                client.starttls(context=context)
                client.ehlo()
            client.login(
                current_app.config["MAIL_USERNAME"],
                current_app.config["MAIL_PASSWORD"],
            )
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise MailDeliveryError(
            "SMTP 서버가 메일을 받지 못했습니다. 서버 주소와 앱 비밀번호를 확인해 주세요."
        ) from error
