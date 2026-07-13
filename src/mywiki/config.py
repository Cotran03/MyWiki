import os
from pathlib import Path
from urllib.parse import urlsplit


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    value = raw_value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false.")


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "sqlite:///mywiki.db")
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://") and "+psycopg" not in value:
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    MAIL_BACKEND = os.getenv("MAIL_BACKEND", "console").strip().lower()
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _env_bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME") or None
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD") or None
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER") or MAIL_USERNAME
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "MyWiki")
    MAIL_TIMEOUT_SECONDS = int(os.getenv("MAIL_TIMEOUT_SECONDS", "10"))
    MAIL_SUBJECT_PREFIX = os.getenv("MAIL_SUBJECT_PREFIX", "[MyWiki]")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    TRASH_RETENTION_DAYS = 30
    AUTH_TOKEN_TTL_SECONDS = 24 * 60 * 60
    RESET_TOKEN_TTL_SECONDS = 60 * 60

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_TIME_LIMIT = 60 * 60

    @classmethod
    def init_app(cls, app) -> None:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)

        base_url = urlsplit(app.config["BASE_URL"])
        if (
            base_url.scheme not in {"http", "https"}
            or not base_url.netloc
            or base_url.username
            or base_url.password
            or base_url.query
            or base_url.fragment
            or base_url.path not in {"", "/"}
        ):
            raise RuntimeError("BASE_URL must be an http(s) origin without a path or credentials.")

        backend = app.config["MAIL_BACKEND"]
        if backend not in {"console", "smtp"}:
            raise RuntimeError("MAIL_BACKEND must be 'console' or 'smtp'.")
        if backend == "smtp":
            if app.config["MAIL_USE_TLS"] and app.config["MAIL_USE_SSL"]:
                raise RuntimeError("MAIL_USE_TLS and MAIL_USE_SSL cannot both be enabled.")
            required = {
                "MAIL_SERVER": app.config["MAIL_SERVER"],
                "MAIL_USERNAME": app.config["MAIL_USERNAME"],
                "MAIL_PASSWORD": app.config["MAIL_PASSWORD"],
                "MAIL_DEFAULT_SENDER": app.config["MAIL_DEFAULT_SENDER"],
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise RuntimeError(f"SMTP configuration is missing: {', '.join(missing)}")
            if not 1 <= app.config["MAIL_PORT"] <= 65535:
                raise RuntimeError("MAIL_PORT must be between 1 and 65535.")
            if app.config["MAIL_TIMEOUT_SECONDS"] <= 0:
                raise RuntimeError("MAIL_TIMEOUT_SECONDS must be positive.")


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True

    @classmethod
    def init_app(cls, app) -> None:
        super().init_app(app)
        if app.config["SECRET_KEY"] == "dev-only-change-me":
            raise RuntimeError("Production requires a strong SECRET_KEY.")
        if app.config["MAIL_BACKEND"] == "console":
            raise RuntimeError("Production requires an SMTP mail backend.")
        if not app.config["BASE_URL"].startswith("https://"):
            raise RuntimeError("Production BASE_URL must use HTTPS.")


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"


CONFIGS = {
    "development": Config,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
