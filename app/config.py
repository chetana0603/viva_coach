"""Environment-based configuration objects."""
import os


def _engine_options(uri: str) -> dict:
    """
    Engine settings, adjusted for the database actually in use.

    On PostgreSQL we disable psycopg's prepared statements. Supabase's
    *transaction* pooler gives each query a different backend connection, so a
    statement prepared on one connection is missing on the next — and reusing the
    name raises `DuplicatePreparedStatement: prepared statement "_pg3_0" already
    exists`. Direct connections and session-mode poolers don't need this, but it
    costs little there, so it is applied to all Postgres URLs.

    SQLite rejects unknown connect args, so it gets none of this.
    """
    options = {"pool_pre_ping": True, "pool_recycle": 280}
    if uri.startswith("postgresql"):
        options.update({
            "pool_size": 5,
            "max_overflow": 5,
            "connect_args": {"prepare_threshold": None},
        })
    return options


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + os.path.join(os.getcwd(), "instance", "viva.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # pool_pre_ping revives connections a managed pooler (Supabase/Render) may have
    # dropped between requests; small pool keeps us well under free-tier limits.
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(SQLALCHEMY_DATABASE_URI)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    WTF_CSRF_TIME_LIMIT = None
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    ALLOWED_EMAIL_DOMAIN = os.environ.get("ALLOWED_EMAIL_DOMAIN", "")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    def __init__(self):
        if not os.environ.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY must be set in production")
