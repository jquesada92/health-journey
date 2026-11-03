"""Real, session-scoped consent gateway BEFORE Gradio's password login.

The Gradio auth_message is informational HTML only, not a trustworthy form
submission. This gate uses a separate server-side form, a signed HttpOnly
session cookie and in-memory consent flags. It never stores health data or
login credentials, and a server restart invalidates all consent sessions.
"""
from __future__ import annotations

import hashlib
import hmac
import html
from ipaddress import ip_address
import os
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

COOKIE_NAME = "hj_privacy_session"
SESSION_SECONDS = 12 * 60 * 60
_SECRET = secrets.token_bytes(32)
_SESSIONS: dict[str, dict] = {}
_LOCK = threading.RLock()

_PAGE = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Privacidad y acceso · Health Journey</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; padding: 24px 14px; font-family: ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
           color: #203046; background: #f6f8fb; line-height: 1.55; }
    main { max-width: 870px; margin: 0 auto; padding: clamp(18px,4vw,34px);
           border: 1px solid #e0e6ee; border-radius: 18px; background: #fff; }
    .eyebrow { font-weight: 750; letter-spacing: .09em; font-size: 11px; color: #127560; }
    h1 { font-size: clamp(23px,4vw,33px); line-height: 1.2; margin: 8px 0 10px; }
    h2 { font-size: 17px; margin: 0 0 8px; }
    h3 { font-size: 15px; margin: 0 0 5px; }
    p { margin: 0 0 12px; }
    .muted { color: #4d5b6f; }
    .small { font-size: 13px; }
    .panel { border: 1px solid #dce5ed; border-radius: 12px; padding: 16px; margin: 16px 0; }
    .grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit,minmax(min(100%,270px),1fr)); }
    .choice { border: 1px solid #dce5ed; border-radius: 12px; padding: 14px; cursor: pointer; }
    .choice strong { display: block; line-height: 1.4; }
    .choice small { display: block; color: #506176; margin: 6px 0 0 27px; font-size: 12px; }
    input[type=checkbox] { width: 18px; height: 18px; margin: 0 8px 0 0; vertical-align: middle; accent-color: #11685e; }
    ul { padding-left: 20px; margin: 7px 0 0; }
    li { margin: 6px 0; }
    .notice { background:#f2f8f7; border-left: 3px solid #168d79; padding: 13px; border-radius: 6px; }
    .ack { display: flex; gap: 10px; align-items: flex-start; padding: 10px 0; }
    .ack input { margin-top: 4px; flex-shrink: 0; }
    .error { color: #9f1d26; background: #fff2f2; padding: 12px; border-radius: 8px; }
    button { display: block; width: 100%; border: 0; border-radius: 10px; background: #11685e;
             color: white; font-weight: 750; font-size: 15px; padding: 14px; cursor: pointer; }
    button:hover,button:focus-visible { background: #0d554b; }
    a { color: #075b8d; }
  </style>
</head>
<body>
<main>
  <div class="eyebrow">HEALTH JOURNEY · PASO PREVIO AL INICIO DE SESIÓN</div>
  <h1>Privacidad, tratamiento de datos y consentimientos</h1>
  <p class="muted">Health Journey reúne información de composición corporal y
  entrenamientos para ayudarte a revisar tu progreso. Antes de iniciar sesión,
  conoce qué datos procesamos y decide qué usos autorizas.</p>

  <section class="panel" aria-labelledby="privacy-info">
    <h2 id="privacy-info">¿Cómo se tratarán tus datos?</h2>
    <ul class="small">
      <li><strong>Qué información:</strong> exámenes InBody (identificador de
      persona, edad, fecha, archivo, mediciones y respuestas de extracción de IA)
      y registros de entrenamiento (fechas, ejercicios, series, repeticiones,
      pesos y comentarios). Son datos personales que pueden revelar información de salud.</li>
      <li><strong>Para qué:</strong> extraer y revisar mediciones, registrar
      entrenamientos y consultar tu historial y evolución. No se publica tu
      información por aceptar el almacenamiento.</li>
      <li><strong>Quién los procesa:</strong> la aplicación Health Journey recibe
      los archivos en su servidor. Si autorizas la IA y pulsas Extraer,
      el documento InBody se envía al servicio externo <strong>Google Gemini</strong>,
      donde se procesa conforme a las condiciones del proveedor. Los CSV de entrenamientos no se envían a Gemini al importarlos,
      pero los resúmenes de entrenamiento e InBody se pueden enviar al chat
      fitness con un permiso separado y al hacer una pregunta.</li>
      <li><strong>Almacenamiento y duración:</strong> si autorizas y confirmas el
      guardado, los datos revisados, el resultado bruto de extracción y sus
      registros de auditoría se guardan en una <strong>base de datos</strong>.
      Permanecen después de cerrar sesión; no se eliminan automáticamente al
      desmarcar un consentimiento.</li>
      <li><strong>Acceso y decisiones:</strong> la consulta del historial privado
      requiere acceso autorizado. Puedes retirar permisos para nuevos envíos
      dentro de la sesión. Para solicitar revisión o eliminación de datos ya
      guardados, contacta al administrador de Health Journey; esta pantalla
      todavía no incluye una función automática de eliminación.</li>
    </ul>
  </section>

  <form method="post" action="/privacy/consent">
    <h2>Elige tus consentimientos</h2>
    <p class="small muted">Son independientes y <strong>opcionales</strong>.
    Los permisos comienzan desactivados. Puedes iniciar sesión sin autorizar ninguno;
    en ese caso no podrás enviar exámenes a la IA ni guardar nuevos datos
    hasta que otorgues el permiso correspondiente.</p>
    <div class="grid">
      <label class="choice">
        <input type="checkbox" name="ai_consent" value="yes">
        <strong>Autorizo enviar mis documentos InBody a Google Gemini</strong>
        <small>Se enviarán únicamente al pulsar Extraer. Un servicio de terceros
        procesará el contenido del documento. Puede contener datos sensibles.</small>
      </label>
      <label class="choice">
        <input type="checkbox" name="db_consent" value="yes">
        <strong>Autorizo guardar mis datos en una base de datos</strong>
        <small>Solo se guardará al pulsar Guardar. Incluye mediciones revisadas,
        respuesta de IA y/o registros de entrenamiento. Persistirán al cerrar sesión.</small>
      </label>
      <label class="choice">
        <input type="checkbox" name="coach_consent" value="yes">
        <strong>Autorizo enviar resúmenes privados de InBody y entrenamientos a Gemini para el chat fitness</strong>
        <small>Solo al enviar cada pregunta. Se comparten tendencias y metas,
        sin identificadores, archivos ni documentos originales. Es un servicio externo
        y sus cuotas y políticas de tratamiento de datos son independientes.</small>
      </label>
    </div>

    <div class="panel">
      <label class="ack">
        <input type="checkbox" name="notice_read" value="yes" required>
        <span class="small">Confirmo que he leído esta explicación sobre el
        tratamiento de datos. <strong>Esta confirmación no activa los dos
        consentimientos opcionales.</strong></span>
      </label>
      <p class="small muted">Tus elecciones se conservan solo durante la sesión,
      se pueden cambiar después de iniciar sesión y no se usarán para publicar
      información. Al cerrar sesión se borran estas elecciones de sesión.</p>
    </div>
    {{error}}
    <button type="submit">Continuar al inicio de sesión</button>
  </form>
</main>
</body>
</html>"""


def render_privacy_page(error: str = "") -> str:
    """A self-contained accessible HTML page; escaped error is never executable."""
    warning = ('<p class="error" role="alert">' + html.escape(error) + '</p>') if error else ""
    return _PAGE.replace("{{error}}", warning)


def _cookie_value(sid: str) -> str:
    signature = hmac.new(_SECRET, sid.encode("ascii"), hashlib.sha256).hexdigest()
    return sid + "." + signature


def _session_from_cookie(value: str | None) -> tuple[str, dict] | None:
    if not isinstance(value, str):
        return None
    try:
        sid, signature = value.rsplit(".", 1)
        if len(sid) < 24 or len(sid) > 100 or not sid.isascii():
            return None
        if not hmac.compare_digest(signature, _cookie_value(sid).rsplit(".", 1)[1]):
            return None
        with _LOCK:
            session = _SESSIONS.get(sid)
            if session is None:
                return None
            if time.time() - session["created"] >= SESSION_SECONDS:
                _SESSIONS.pop(sid, None)
                return None
            return sid, session.copy()
    except (ValueError, UnicodeError):
        return None


def _consent_session(request) -> tuple[str, dict] | None:
    """Accept either a Starlette Request or Gradio's injected gr.Request."""
    origin_request = getattr(request, "request", request)
    cookies = getattr(origin_request, "cookies", {})
    return _session_from_cookie(cookies.get(COOKIE_NAME))


def current_choices(request) -> tuple[bool, bool]:
    session = _consent_session(request)
    return (session[1]["ai"], session[1]["db"]) if session else (False, False)


def coach_choice(request) -> bool:
    session = _consent_session(request)
    return bool(session and session[1].get("coach") is True)


def has_consent(request, scope: str) -> bool:
    """Fail closed when the pre-login choice is absent, revoked or expired."""
    if scope not in {"ai", "db", "coach"}:
        raise ValueError("Invalid consent scope.")
    session = _consent_session(request)
    return bool(session and session[1][scope] is True)


def set_consent(request, scope: str, value: bool) -> None:
    """Update server-authoritative consent on an explicit UI checkbox event."""
    if scope not in {"ai", "db", "coach"} or not isinstance(value, bool):
        raise ValueError("Invalid consent update.")
    session = _consent_session(request)
    if not session:
        raise PermissionError("La sesión ha caducado. Vuelve a revisar el consentimiento.")
    sid, _ = session
    with _LOCK:
        if sid not in _SESSIONS:
            raise PermissionError("La sesión ha caducado.")
        _SESSIONS[sid][scope] = value


def _revoke(request) -> None:
    result = _consent_session(request)
    if result:
        with _LOCK:
            _SESSIONS.pop(result[0], None)


async def privacy_page(request):
    response = HTMLResponse(render_privacy_page())
    response.headers["Cache-Control"] = "no-store"
    return response


async def submit_consent(request):
    """The browser form is the source of pre-login opt-in; never auto-opt in."""
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).hostname != request.url.hostname:
        return HTMLResponse(render_privacy_page("Solicitud de otro origen rechazada."), status_code=403)
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        return HTMLResponse(render_privacy_page("Solicitud de otro sitio rechazada."), status_code=403)
    data = await request.body()
    if len(data) > 8192:
        return HTMLResponse(render_privacy_page("Formulario demasiado grande."), status_code=413)
    form = parse_qs(data.decode("utf-8", errors="replace"), keep_blank_values=True)
    if form.get("notice_read") != ["yes"]:
        return HTMLResponse(render_privacy_page("Confirma que leíste el aviso de datos."), status_code=400)
    if any(name not in {"notice_read", "ai_consent", "db_consent", "coach_consent"} for name in form):
        return HTMLResponse(render_privacy_page("Formulario inválido."), status_code=400)
    if any(value != ["yes"] for value in form.values()):
        return HTMLResponse(render_privacy_page("Valor de autorización inválido."), status_code=400)

    sid = secrets.token_urlsafe(32)
    with _LOCK:
        # Lazy cleanup; no sensitive data nor credentials live in this store.
        now = time.time()
        for old_sid, state in list(_SESSIONS.items()):
            if now - state["created"] >= SESSION_SECONDS:
                _SESSIONS.pop(old_sid, None)
        _SESSIONS[sid] = {
            "created": now,
            "ai": form.get("ai_consent") == ["yes"],
            "db": form.get("db_consent") == ["yes"],
            "coach": form.get("coach_consent") == ["yes"],
        }
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME, _cookie_value(sid), path="/", httponly=True,
        secure=bool(os.environ.get("SPACE_ID")), samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _internal_startup_request(request, path: str) -> bool:
    """Permit Gradio's *local* startup handshake, never arbitrary API access.

    Gradio's launch() calls http://localhost:<port>/gradio_api/startup-events
    before the first browser can receive a consent cookie. Redirecting that
    self-check to /privacy returns HTTP 303 and aborts the application boot.

    Trust only the actual TCP peer address; Host, Origin, X-Forwarded-For and
    other client-controlled proxy headers MUST NOT grant an exception.
    """
    if path != "/gradio_api/startup-events" or request.method != "GET":
        return False
    peer = getattr(request.client, "host", None)
    try:
        address = ip_address(peer)
    except (ValueError, TypeError):
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    return address.is_loopback or bool(mapped and mapped.is_loopback)


class PrivacyFirstMiddleware(BaseHTTPMiddleware):
    """Require privacy choices for users without breaking local Gradio boot."""

    async def dispatch(self, request, call_next):
        path = request.url.path.rstrip("/") or "/"
        # Gradio performs this GET locally during launch(), before anyone has
        # accepted the privacy notice. No other endpoint is exempted.
        if _internal_startup_request(request, path):
            return await call_next(request)
        if path == "/privacy" and request.method == "GET":
            return await call_next(request)
        if path == "/privacy/consent" and request.method == "POST":
            return await call_next(request)
        if _consent_session(request) is None:
            if request.method in ("GET", "HEAD"):
                return RedirectResponse("/privacy", status_code=303)
            return JSONResponse({"detail": "Primero revisa los permisos de datos."}, status_code=403)
        response = await call_next(request)
        if path == "/logout":
            _revoke(request)
            response.delete_cookie(COOKIE_NAME, path="/")
        return response
