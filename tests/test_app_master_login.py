"""Synthetic master-demo authentication and private data access tests.

No real Neon credentials, passwords or network requests.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from inbody_mvp import app_auth, storage


def test_password_hash_roundtrip_and_bad_password():
    stored = app_auth.hash_password("synthetic-very-long-password", salt=b"synthetic-salt-24-bytes!!!")
    assert stored.startswith("pbkdf2_sha256$")
    assert "synthetic-very-long-password" not in stored
    assert app_auth.verify_password("synthetic-very-long-password", stored)
    assert not app_auth.verify_password("incorrect-password", stored)
    assert not app_auth.verify_password("password", "garbled")


def test_master_login_is_disabled_without_explicit_flag(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://synthetic:synthetic@host/db?sslmode=require")
    monkeypatch.delenv("ENABLE_APP_PASSWORD_LOGIN", raising=False)
    assert not app_auth.password_login_enabled()
    assert not app_auth.authenticate_master_demo("obs-master-demo", "test")
    monkeypatch.setenv("ENABLE_APP_PASSWORD_LOGIN", "1")
    assert app_auth.password_login_enabled()


def test_gradio_password_auth_stores_only_hash_and_resets_failures(monkeypatch):
    monkeypatch.setenv("ENABLE_APP_PASSWORD_LOGIN", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://synthetic:synthetic@host/db?sslmode=require")
    pwd = "synthetic-secure-password"
    record = {
        "username": "obs-master-demo",
        "password_hash": app_auth.hash_password(pwd, salt=b"other-synthetic-salt!!"),
        "enabled": True,
        "failed_attempts": 0,
        "locked_until": None,
    }
    changes = []

    class Connection:
        def execute(self, query, params):
            sql = str(query)
            if sql.lstrip().startswith("SELECT"):
                return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: record))
            changes.append((sql, params))
            return SimpleNamespace()
    class Transaction:
        def __enter__(self):
            return Connection()
        def __exit__(self, *_):
            return False
    class Engine:
        def begin(self):
            return Transaction()
        def dispose(self):
            pass

    monkeypatch.setattr(app_auth, "_engine", lambda: Engine())
    assert app_auth.authenticate_master_demo("obs-master-demo", pwd)
    assert len(changes) == 1
    assert "last_login_at" in changes[0][0]
    assert not app_auth.authenticate_master_demo("obs-master-demo", "incorrect")
    assert "locked_until" in changes[-1][0]
    assert not app_auth.authenticate_master_demo("another-user", pwd)


def test_locked_account_cannot_login(monkeypatch):
    monkeypatch.setenv("ENABLE_APP_PASSWORD_LOGIN", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://synthetic:synthetic@host/db?sslmode=require")
    record = {
        "username": "obs-master-demo",
        "password_hash": app_auth.hash_password("synthetic-test-password"),
        "enabled": True, "failed_attempts": 4,
        "locked_until": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    class Connection:
        def execute(self, query, params):
            return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: record))
    class Transaction:
        def __enter__(self):
            return Connection()
        def __exit__(self, *_):
            return False
    class Engine:
        def begin(self):
            return Transaction()
        def dispose(self):
            pass
    monkeypatch.setattr(app_auth, "_engine", lambda: Engine())
    assert not app_auth.authenticate_master_demo("obs-master-demo", "synthetic-test-password")


def test_private_history_accepts_only_trusted_gradio_user_or_oauth(monkeypatch):
    monkeypatch.setenv("ENABLE_APP_PASSWORD_LOGIN", "1")
    monkeypatch.setenv("SPACE_ID", "test/space")
    monkeypatch.setenv("ENABLE_PERSISTENCE", "0")
    monkeypatch.setenv("DATABASE_URL", "postgresql://synthetic:synthetic@host/db?sslmode=require")
    monkeypatch.delenv("HF_ALLOWED_USERS", raising=False)
    assert storage.database_enabled()
    with pytest.raises(PermissionError):
        storage.require_database_access()
    with pytest.raises(PermissionError):
        storage.require_database_access(request=SimpleNamespace(username="not-master"))
    storage.require_database_access(request=SimpleNamespace(username="obs-master-demo"))
    monkeypatch.setenv("ENABLE_APP_PASSWORD_LOGIN", "0")
    with pytest.raises(PermissionError):
        storage.require_database_access(request=SimpleNamespace(username="obs-master-demo"))


def test_app_auth_wired_to_real_gradio_request_not_client_input():
    from pathlib import Path
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text()
    assert "auth=authenticate_master_demo if password_login_enabled() else None" in app
    assert "request: gr.Request | None = None" in app
    assert "request=request" in app
    assert "interactive=(not anonymous_demo_requested() or password_login_enabled())" in app
    assert "password" not in app.lower().split("auth=authenticate_master_demo")[1].split("\n", 3)[0]


def test_no_plaintext_password_in_account_migration():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "migrations/006_app_master_demo_account.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS public.hj_app_accounts" in source
    assert "password_hash text NOT NULL" in source
    assert "REVOKE ALL ON TABLE public.hj_app_accounts FROM PUBLIC" in source
    assert "INSERT INTO public.hj_app_accounts" not in source
