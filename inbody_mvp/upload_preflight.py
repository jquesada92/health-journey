"""Read-only duplicate preflight before a token-consuming InBody extraction.

A private, parameterized filename existence query runs before Gemini.
The report bytes never leave the application during this check.
"""
from __future__ import annotations

import hashlib

from .gemini_review import check_processed_filename


def preflight_processed_upload(upload_state, *, profile=None, request=None) -> dict:
    """Return explicit duplicate state bound to a local byte fingerprint.

    The private database function tests the filename, not the document hash.
    If unavailable, report unverified rather than falsely claiming new.
    """
    if not isinstance(upload_state, dict):
        return {
            "status": "empty", "sha256": None,
            "message": "Selecciona un archivo para verificar duplicados.",
        }
    name = upload_state.get("filename")
    data = upload_state.get("data")
    if not isinstance(name, str) or not name or not isinstance(data, bytes):
        return {
            "status": "empty", "sha256": None,
            "message": "El archivo seleccionado es inválido. Cárgalo de nuevo.",
        }
    fingerprint = hashlib.sha256(data).hexdigest()
    message = check_processed_filename(
        upload_state, profile=profile, request=request
    )
    if message.startswith("Este nombre de archivo ya fue procesado"):
        return {
            "status": "duplicate", "sha256": fingerprint,
            "message": "Archivo ya procesado. Extracción bloqueada para ahorrar tokens.",
        }
    if message.startswith("Archivo nuevo:"):
        return {
            "status": "new", "sha256": fingerprint,
            "message": "Archivo no registrado por nombre. Puedes extraer sus mediciones.",
        }
    return {
        "status": "unverified", "sha256": fingerprint,
        "message": (
            "No fue posible verificar si este nombre ya existe en la base de datos. "
            "Puedes continuar, pero podrías consumir tokens de un archivo duplicado."
        ),
    }
