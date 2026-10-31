"""URLs de autenticación HF en pestaña independiente.

Evita la autenticación en iframes, donde algunas cookies OAuth no persisten.
Nunca contiene tokens, secretos, IDs personales ni URLs no verificadas.
"""
from __future__ import annotations

import re

_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,250}[a-z0-9])?\.hf\.space$", re.IGNORECASE)


def standalone_oauth_urls(space_host: str | None) -> dict[str, str] | None:
    """Returns only HTTPS URLs belonging to a real *.hf.space hostname.

    HF Spaces provides SPACE_HOST. Do not use SPACE_ID to invent a hostname.
    Gradio's OAuth middleware implements /login/huggingface and /logout.
    """
    raw = (space_host or "").strip()
    if not raw or any(char in raw for char in ("/", ":", "@", "?", "#", " ", "\\", "<", ">")):
        return None
    # SPACE_HOST can be a comma-delimited list with custom domains. Use
    # the first canonical hf.space host if present.
    hosts = [host.strip().lower() for host in raw.split(",")]
    valid = next((host for host in hosts if _HOST_RE.fullmatch(host)), None)
    if valid is None:
        return None
    base = "https://" + valid
    return {
        "app": base + "/",
        "login": base + "/login/huggingface",
        "logout": base + "/logout",
    }
