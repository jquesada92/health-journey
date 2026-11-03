"""Privacy disclosure and REAL pre-login opt-ins; no Gradio or database needed."""
from types import SimpleNamespace

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from inbody_mvp import prelogin_consent as privacy


async def protected(_):
    return PlainTextResponse("protected")


async def logout(_):
    return PlainTextResponse("logged out")


def make_test_app():
    return Starlette(
        routes=[
            Route("/privacy", privacy.privacy_page, methods=["GET"]),
            Route("/privacy/consent", privacy.submit_consent, methods=["POST"]),
            Route("/", protected),
            Route("/login", protected, methods=["POST"]),
            Route("/api/predict", protected, methods=["POST"]),
            Route("/logout", logout),
        ],
        middleware=[Middleware(privacy.PrivacyFirstMiddleware)],
    )


def _gradio_request(client):
    return SimpleNamespace(request=SimpleNamespace(cookies=client.cookies))


def test_no_login_or_api_access_until_privacy_page_submitted():
    with TestClient(make_test_app()) as client:
        first = client.get("/", follow_redirects=False)
        assert first.status_code == 303
        assert first.headers["location"] == "/privacy"
        assert client.post("/login").status_code == 403
        assert client.post("/api/predict").status_code == 403
        page = client.get("/privacy")
        assert page.status_code == 200
        assert "Tratamiento de datos" in page.text or "tratamiento de datos" in page.text
        assert "Google Gemini" in page.text
        assert "base de datos" in page.text
        assert "name=\"ai_consent\"" in page.text
        assert "name=\"db_consent\"" in page.text
        assert "checked" not in page.text.lower()
        assert "required" in page.text
        assert "identificador" in page.text
        assert "datos personales" in page.text
        assert "duración" in page.text.lower()
        assert "eliminación" in page.text.lower()
        assert "Neon" not in page.text


def test_both_optional_consents_default_to_false_and_acknowledgment_required():
    with TestClient(make_test_app()) as client:
        denied = client.post("/privacy/consent", data={})
        assert denied.status_code == 400
        assert client.get("/", follow_redirects=False).status_code == 303
        response = client.post(
            "/privacy/consent", data={"notice_read": "yes"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert privacy.current_choices(_gradio_request(client)) == (False, False)
        assert not privacy.has_consent(_gradio_request(client), "ai")
        assert not privacy.has_consent(_gradio_request(client), "db")
        assert client.get("/").status_code == 200


def test_prelogin_opt_ins_are_independent_and_revocable_after_login():
    with TestClient(make_test_app()) as client:
        response = client.post(
            "/privacy/consent", data={"notice_read": "yes", "ai_consent": "yes"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        request = _gradio_request(client)
        assert privacy.current_choices(request) == (True, False)
        privacy.set_consent(request, "ai", False)
        privacy.set_consent(request, "db", True)
        assert privacy.current_choices(request) == (False, True)
        assert not privacy.has_consent(request, "ai")
        assert privacy.has_consent(request, "db")
        client.get("/logout")
        assert privacy.current_choices(_gradio_request(client)) == (False, False)
        assert client.get("/", follow_redirects=False).status_code == 303


def test_prelogin_storage_opt_in_independent_from_ai():
    with TestClient(make_test_app()) as client:
        client.post(
            "/privacy/consent",
            data={"notice_read": "yes", "db_consent": "yes"},
            follow_redirects=False,
        )
        assert privacy.current_choices(_gradio_request(client)) == (False, True)


def test_signed_cookie_tampering_fails_closed():
    with TestClient(make_test_app()) as client:
        client.post("/privacy/consent", data={"notice_read": "yes", "ai_consent": "yes"})
        valid = client.cookies.get(privacy.COOKIE_NAME)
        assert valid
        forged = valid[:-1] + ("a" if valid[-1] != "a" else "b")
        assert privacy._session_from_cookie(forged) is None
        assert privacy._session_from_cookie(valid) is not None


def test_cross_site_request_cannot_grant_consents():
    with TestClient(make_test_app()) as client:
        r = client.post(
            "/privacy/consent", data={
                "notice_read": "yes", "ai_consent": "yes", "db_consent": "yes",
            },
            headers={"origin": "https://untrusted.example"},
        )
        assert r.status_code == 403
        assert client.get("/", follow_redirects=False).status_code == 303


def test_source_requires_signed_session_at_actual_ai_and_db_callbacks():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app.py").read_text()
    assert "PrivacyFirstMiddleware" in source
    assert 'Route("/privacy", privacy_page, methods=["GET"])' in source
    assert 'Route("/privacy/consent", submit_consent, methods=["POST"])' in source
    assert 'not has_consent(request, "ai")' in source
    assert source.count('not has_consent(request, "db")') == 2
    assert "fn=restore_session_consents" in source
    assert "set_consent(request, \"ai\", value)" in source
    assert "set_consent(request, \"db\", value)" in source
    assert "auth=authenticate_master_demo if password_login_enabled() else None" in source
