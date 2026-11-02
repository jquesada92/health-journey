"""Dedicated password login for an explicitly provisioned app-level demo master.

Credentials are hashed with PBKDF2-HMAC-SHA256 and stored in Neon, never in
GitHub. Gradio's server-side auth callback verifies a password and returns
a trusted gr.Request.username. Private database reads still check authorization.
Do not use this basic password gate for sensitive multi-user production without
additional controls (MFA, audit trail, ingress rate limiting).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url


MASTER_DEMO_USERNAME = "obs-master-demo"
HASH_ITERATIONS = 600_000


def password_login_enabled() -> bool:
    return (
        os.getenv("ENABLE_APP_PASSWORD_LOGIN", "").strip().lower()
        in {"1", "true", "yes"}
        and bool(os.getenv("DATABASE_URL", "").strip())
    )


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Create a password verifier, never log or persist the plaintext."""
    if len(password) < 16:
        raise ValueError("La contraseña debe tener al menos 16 caracteres.")
    salt = salt if salt is not None else secrets.token_bytes(24)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, HASH_ITERATIONS
    )
    return "pbkdf2_sha256$%d$%s$%s" % (
        HASH_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        digest.hex(),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, count, salt, digest = encoded.split("$")
        rounds = int(count)
        if scheme != "pbkdf2_sha256" or rounds < 200_000 or rounds > 1_000_000:
            return False
        salt_bytes = base64.urlsafe_b64decode(salt.encode("ascii"))
        expected = bytes.fromhex(digest)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt_bytes, rounds
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError, UnicodeError, OverflowError):
        return False


def _engine():
    from sqlalchemy import create_engine
    url = os.getenv("DATABASE_URL", "")
    parsed = make_url(url)
    if parsed.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise RuntimeError("Solo se permite PostgreSQL para el login.")
    if parsed.query.get("sslmode") != "require":
        raise RuntimeError("DATABASE_URL debe usar sslmode=require.")
    if parsed.drivername == "postgresql":
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return create_engine(url, pool_pre_ping=True, pool_size=1, max_overflow=0)


def authenticate_master_demo(username: str, password: str) -> bool:
    """Gradio auth callback: fail closed, lock repeated failures."""
    if not password_login_enabled():
        return False
    if not (
        isinstance(username, str) and username.casefold() == MASTER_DEMO_USERNAME
        and isinstance(password, str) and password
    ):
        return False
    try:
        engine = _engine()
        try:
            with engine.begin() as conn:
                record = conn.execute(
                    text("""
                        SELECT username, password_hash, enabled,
                               failed_attempts, locked_until
                        FROM public.hj_app_accounts
                        WHERE username = :username
                        FOR UPDATE
                    """),
                    {"username": MASTER_DEMO_USERNAME},
                ).mappings().first()
                if not record or not record["enabled"]:
                    return False
                now = datetime.now(timezone.utc)
                locked_until = record["locked_until"]
                if locked_until is not None and locked_until > now:
                    return False
                verified = verify_password(password, record["password_hash"])
                if verified:
                    conn.execute(text("""
                        UPDATE public.hj_app_accounts
                           SET failed_attempts = 0, locked_until = NULL,
                               last_login_at = now()
                         WHERE username = :username
                    """), {"username": MASTER_DEMO_USERNAME})
                    return True
                failed = int(record["failed_attempts"]) + 1
                conn.execute(text("""
                    UPDATE public.hj_app_accounts
                       SET failed_attempts = :failures,
                           locked_until = CASE
                             WHEN :failures >= 5 THEN now() + interval '15 minutes'
                             ELSE NULL END
                     WHERE username = :username
                """), {"username": MASTER_DEMO_USERNAME, "failures": failed if failed < 5 else 0})
                # When the threshold is reached, preserve lockout even
                # though failed_attempts is reset for the next window.
                return False
        finally:
            engine.dispose()
    except Exception:
        # Never leak database access or credential errors through login.
        return False


def master_demo_authenticated(request) -> bool:
    """Only Gradio-injected, server-verified username is trusted."""
    return bool(
        password_login_enabled()
        and request is not None
        and getattr(request, "username", None) == MASTER_DEMO_USERNAME
    )
