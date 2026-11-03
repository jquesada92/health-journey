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


async def startup_events(_):
    return PlainTextResponse("startup ready")


def make_test_app():
    return Starlette(
        routes=[
            Route("/privacy", privacy.privacy_page, methods=["GET"]),
            Route("/privacy/consent", privacy.submit_consent, methods=["POST"]),
            Route("/", protected),
            Route("/gradio_api/startup-events", startup_events, methods=["GET"]),
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


def test_fitness_chat_has_third_independent_opt_in_and_can_revoke():
    with TestClient(make_test_app()) as client:
        privacy_page = client.get("/privacy")
        assert 'name="coach_consent"' in privacy_page.text
        client.post(
            "/privacy/consent",
            data={"notice_read": "yes", "coach_consent": "yes"},
            follow_redirects=False,
        )
        request = _gradio_request(client)
        assert privacy.coach_choice(request)
        assert privacy.has_consent(request, "coach")
        assert not privacy.has_consent(request, "ai")
        assert not privacy.has_consent(request, "db")
        assert privacy.current_choices(request) == (False, False)
        privacy.set_consent(request, "coach", False)
        assert not privacy.coach_choice(request)
        assert not privacy.has_consent(request, "coach")


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


def test_gradio_local_startup_endpoint_works_before_privacy_consent():
    """Regression: Gradio launch() GET to localhost must return 200, not 303."""
    with TestClient(make_test_app(), client=("127.0.0.1", 43112)) as client:
        response = client.get("/gradio_api/startup-events", follow_redirects=False)
        assert response.status_code == 200
        assert response.text == "startup ready"
        # Only the internal startup GET is exempt; credentials and data remain gated.
        assert client.get("/", follow_redirects=False).status_code == 303
        assert client.post("/api/predict").status_code == 403
        assert client.post("/login").status_code == 403


def test_startup_exemption_does_not_trust_forged_proxy_headers():
    """External users cannot bypass consent by spoofing localhost headers."""
    with TestClient(make_test_app(), client=("203.0.113.10", 50700)) as client:
        response = client.get(
            "/gradio_api/startup-events",
            headers={
                "Host": "localhost:7860",
                "X-Forwarded-For": "127.0.0.1",
                "X-Real-IP": "127.0.0.1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/privacy"


def test_internal_startup_exception_is_only_exact_get_and_loopback():
    from types import SimpleNamespace
    fake = lambda ip, method="GET": SimpleNamespace(
        method=method, client=SimpleNamespace(host=ip),
    )
    allow = privacy._internal_startup_request
    assert allow(fake("::1"), "/gradio_api/startup-events")
    assert allow(fake("127.0.0.2"), "/gradio_api/startup-events")
    assert not allow(fake("203.0.113.10"), "/gradio_api/startup-events")
    assert not allow(fake("localhost"), "/gradio_api/startup-events")
    assert not allow(fake("127.0.0.1", "POST"), "/gradio_api/startup-events")
    assert not allow(fake("127.0.0.1"), "/gradio_api/predict")
    assert not allow(fake("127.0.0.1"), "/login")
