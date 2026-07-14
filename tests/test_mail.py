import pytest

from mywiki.services import mail as mail_service

from .conftest import create_user


class FakeSMTP:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.message = None
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def ehlo(self):
        self.calls.append(("ehlo",))

    def starttls(self, *, context):
        self.calls.append(("starttls", context))

    def login(self, username, password):
        self.calls.append(("login", username, password))

    def send_message(self, message):
        self.calls.append(("send_message",))
        self.message = message

    def noop(self):
        self.calls.append(("noop",))
        return 250, b"OK"


def configure_smtp(app):
    app.config.update(
        BASE_URL="https://wiki.example",
        MAIL_BACKEND="smtp",
        MAIL_SERVER="smtp.gmail.com",
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_USERNAME="sender@example.com",
        MAIL_PASSWORD="app-password",
        MAIL_DEFAULT_SENDER="sender@example.com",
        MAIL_FROM_NAME="MyWiki",
        MAIL_TIMEOUT_SECONDS=10,
        MAIL_SUBJECT_PREFIX="[MyWiki]",
    )


def test_smtp_verification_email_uses_tls_and_trusted_base_url(app, monkeypatch):
    FakeSMTP.instances.clear()
    configure_smtp(app)
    monkeypatch.setattr(mail_service.smtplib, "SMTP", FakeSMTP)

    with app.app_context():
        user = create_user("alice", verified=False)
        with app.test_request_context("/", headers={"Host": "evil.example"}):
            mail_service.send_verification_message(user, "secret-token")

    smtp = FakeSMTP.instances[-1]
    assert smtp.kwargs == {"host": "smtp.gmail.com", "port": 587, "timeout": 10}
    assert [call[0] for call in smtp.calls] == [
        "ehlo",
        "starttls",
        "ehlo",
        "login",
        "send_message",
    ]
    assert ("login", "sender@example.com", "app-password") in smtp.calls
    assert smtp.message["To"] == "alice@example.com"
    assert smtp.message["From"] == "MyWiki <sender@example.com>"
    assert smtp.message["Subject"] == "[MyWiki] 이메일 인증"

    plain_body = smtp.message.get_body(preferencelist=("plain",)).get_content()
    html_body = smtp.message.get_body(preferencelist=("html",)).get_content()
    expected_url = "https://wiki.example/auth/verify/secret-token"
    assert expected_url in plain_body
    assert expected_url in html_body
    assert "https://wiki.example/static/img/MyWiki.png" in html_body
    assert "evil.example" not in plain_body


def test_smtp_errors_are_reported_without_leaking_provider_exception(app, monkeypatch):
    configure_smtp(app)

    def fail_to_connect(**kwargs):
        raise OSError("provider detail")

    monkeypatch.setattr(mail_service.smtplib, "SMTP", fail_to_connect)

    with app.app_context(), pytest.raises(mail_service.MailDeliveryError) as error:
        mail_service.send_test_message("recipient@example.com")

    assert "SMTP 서버" in str(error.value)
    assert "provider detail" not in str(error.value)


def test_send_test_email_cli_uses_configured_backend(app, monkeypatch):
    FakeSMTP.instances.clear()
    configure_smtp(app)
    monkeypatch.setattr(mail_service.smtplib, "SMTP", FakeSMTP)

    result = app.test_cli_runner().invoke(args=["send-test-email", "recipient@example.com"])

    assert result.exit_code == 0
    assert "recipient@example.com" in result.output
    assert FakeSMTP.instances[-1].message["To"] == "recipient@example.com"


def test_check_smtp_cli_authenticates_without_sending_email(app, monkeypatch):
    FakeSMTP.instances.clear()
    configure_smtp(app)
    monkeypatch.setattr(mail_service.smtplib, "SMTP", FakeSMTP)

    result = app.test_cli_runner().invoke(args=["check-smtp"])

    assert result.exit_code == 0
    assert "no email was sent" in result.output
    smtp = FakeSMTP.instances[-1]
    assert [call[0] for call in smtp.calls] == [
        "ehlo",
        "starttls",
        "ehlo",
        "login",
        "noop",
    ]
    assert smtp.message is None
