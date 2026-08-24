# backend/database.py
import config  # Loads backend/.env once with process env precedence.
import os
import ssl
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_default_db_path = os.path.join(os.path.dirname(__file__), "vendorscope.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_db_path}")

# Normalise URL dialect:
#   postgres://   → postgresql+pg8000://  (Neon/Render shorthand)
#   postgresql:// → postgresql+pg8000://  (standard, no driver specified)
# pg8000 is pure-Python — works on any Python version including 3.14+
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    _connect_args: dict = {"check_same_thread": False}
else:
    # pg8000 doesn't accept sslmode/channel_binding as URL query params —
    # strip them from the URL and pass an ssl_context object instead.
    _parsed = urlparse(DATABASE_URL)
    _params = {k: v[0] for k, v in parse_qs(_parsed.query).items()
               if k not in ("sslmode", "channel_binding")}
    DATABASE_URL = urlunparse(_parsed._replace(query=urlencode(_params)))

    # Supabase Session Pooler uses a self-signed cert not in any standard CA bundle.
    # CERT_NONE: cert authenticity unverified, but connection is still TLS-encrypted.
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE
    _connect_args = {"ssl_context": _ssl_ctx}

# Cloud PostgreSQL needs pre-ping to recover stale connections after idle periods
_engine_kwargs: dict = {"connect_args": _connect_args}
if not _is_sqlite:
    _engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 240,   # Recycle before ~300s idle timeout kills connections
        # Overridable so a transient batch process (e.g. the Modal nightly-scan
        # container) can run a smaller pool than the always-on app without a
        # second copy of this connection logic.
        "pool_size": int(os.getenv("DB_POOL_SIZE", 3)),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", 5)),
        "pool_timeout": 30,    # Don't block indefinitely waiting for a connection
    })

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
