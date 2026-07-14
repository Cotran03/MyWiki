import os
from pathlib import Path
from uuid import uuid4

import click
from dotenv import load_dotenv
from flask import Flask, g, render_template, request
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from .extensions import csrf, db, limiter, login_manager, migrate


def create_app(test_config: dict | None = None) -> Flask:
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")

    from .config import CONFIGS

    env_name = (
        "testing"
        if test_config and test_config.get("TESTING")
        else os.getenv("APP_ENV", "development")
    )
    config_class = CONFIGS.get(env_name, CONFIGS["development"])

    app = Flask(
        __name__,
        instance_relative_config=True,
        instance_path=str(project_root / "instance"),
    )
    app.config.from_object(config_class)
    if test_config:
        app.config.update(test_config)
    config_class.init_app(app)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "로그인이 필요한 페이지입니다."
    login_manager.login_message_category = "warning"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, user_id)

    from .auth import bp as auth_bp
    from .documents import bp as documents_bp
    from .main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)

    register_request_hooks(app)
    register_error_handlers(app)
    register_cli(app)

    return app


def register_request_hooks(app: Flask) -> None:
    @app.before_request
    def assign_request_id() -> None:
        g.request_id = request.headers.get("X-Request-ID", str(uuid4()))[:64]

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "style-src 'self' https://cdn.jsdelivr.net; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        response.headers["X-Request-ID"] = g.get("request_id", "")
        return response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(OperationalError)
    @app.errorhandler(SQLAlchemyTimeoutError)
    def database_unavailable(error):
        db.session.rollback()
        app.logger.error(
            "Database unavailable | request_id=%s error_type=%s",
            g.get("request_id", ""),
            type(error).__name__,
        )
        return render_template("errors/503.html"), 503

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(409)
    def conflict(error):
        return render_template("errors/409.html"), 409

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create tables for a local throwaway database."""
        db.create_all()
        print("Database tables created. Use migrations for shared environments.")

    @app.cli.command("send-test-email")
    @click.argument("recipient")
    def send_test_email_command(recipient: str) -> None:
        """Send a message through the configured mail backend."""
        from email_validator import EmailNotValidError, validate_email

        from .services.mail import MailDeliveryError, send_test_message

        try:
            normalized_recipient = validate_email(
                recipient,
                check_deliverability=False,
            ).normalized
        except EmailNotValidError as error:
            raise click.ClickException(str(error)) from error

        try:
            send_test_message(normalized_recipient)
        except MailDeliveryError as error:
            raise click.ClickException(str(error)) from error
        click.echo(f"Test email accepted by the mail backend for {normalized_recipient}.")

    @app.cli.command("check-smtp")
    def check_smtp_command() -> None:
        """Authenticate to SMTP without sending a message."""
        from .services.mail import MailDeliveryError, check_smtp_connection

        try:
            check_smtp_connection()
        except MailDeliveryError as error:
            raise click.ClickException(str(error)) from error
        click.echo("SMTP connection and authentication succeeded; no email was sent.")

    @app.shell_context_processor
    def shell_context() -> dict:
        from . import models

        return {"db": db, "models": models}
