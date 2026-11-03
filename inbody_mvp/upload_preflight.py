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
            "message": (
                "Este archivo ya está guardado. Para corregirlo, activa "
                "'Reprocesar y reemplazar el archivo existente' y vuelve "
                "a extraerlo (volver a extraer consume tokens). El anterior " 
                "solo se sustituye al guardar "
                "las mediciones revisadas."
            ),
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


def assert_private_filename_replacement(upload_state, *, profile=None, request=None):
    """Pre-authorize same-person replacement BEFORE spending Gemini tokens.

    Do not reveal the personal identifier or the existing medical rows.
    The dedicated private stored procedure checks everything again when
    the confirmed correction is saved.
    """
    from sqlalchemy import text
    from .coach_data import resolve_private_person_id
    from .storage import (
        _database_engine, canonical_person_id, require_database_access,
    )

    require_database_access(oauth_profile=profile, request=request)
    if not isinstance(upload_state, dict):
        raise ValueError("Selecciona el archivo que deseas reemplazar.")
    filename = upload_state.get("filename")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("No se encontró un nombre de archivo válido.")
    person_key = canonical_person_id(
        resolve_private_person_id(profile=profile, request=request)
    )
    engine = _database_engine()
    try:
        with engine.connect() as connection:
            allowed = connection.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM public.hj_extraction_audits e
                        JOIN public.hj_person_aliases p
                          ON p.anonymous_id = e.anonymous_id
                        WHERE lower(btrim(e.filename)) = lower(btrim(:filename))
                          AND p.normalized_person_id = :person_id
                    )
                """),
                {"filename": filename, "person_id": person_key},
            ).scalar_one()
    finally:
        engine.dispose()
    if not allowed:
        raise PermissionError(
            "No puedes reemplazar este archivo: no pertenece al "
            "historial privado autorizado o no está registrado."
        )
