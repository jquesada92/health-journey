"""Isolated, no-login classroom demo persistence.

Stores only selected numeric metrics, a random UUID alias, date-only and a
sanitized device group. NEVER stores the report ID, name, age, OCR, source
hash or uploaded bytes. Uses its own restricted SQL role/function.
"""
from __future__ import annotations

import json
import os
from uuid import UUID

from sqlalchemy import create_engine, text

from .public_dashboard import PUBLIC_METRICS
from .storage import ConfirmedExam


_ALLOWED_UNITS = {
    "weight": "kg",
    "skeletal_muscle_mass": "kg",
    "body_fat_mass": "kg",
    "body_fat_percentage": "%",
    "total_body_water": "L",
    "segmental_lean_mass": "kg",
    "segmental_fat_mass": "kg",
    "phase_angle": "°",
}
_ALLOWED_SEGMENTS = {
    "left_arm", "right_arm", "left_leg", "right_leg", "trunk", "whole_body",
}


def anonymous_demo_requested() -> bool:
    return os.getenv("ENABLE_ANONYMOUS_DEMO", "").strip().lower() in (
        "1", "true", "yes",
    )


def anonymous_demo_enabled() -> bool:
    """Explicitly enabled ONLY with a dedicated writer secret."""
    return anonymous_demo_requested() and bool(os.getenv("DEMO_DATABASE_URL"))


def _demo_database_engine():
    uri = os.getenv("DEMO_DATABASE_URL", "")
    if uri.startswith("postgresql://"):
        uri = "postgresql+psycopg://" + uri[len("postgresql://"):]
    if not uri.startswith("postgresql+psycopg://") or "sslmode=require" not in uri:
        raise RuntimeError("DEMO_DATABASE_URL debe usar PostgreSQL y sslmode=require.")
    return create_engine(uri, pool_pre_ping=True, pool_size=1, max_overflow=0)


def anonymized_measurements(report: ConfirmedExam) -> list[dict]:
    """Strict allowlist; discard all free text, labels and source metadata."""
    filtered = []
    for measure in report.measurements:
        if measure.variable_medida not in PUBLIC_METRICS:
            continue
        if measure.unidad_medida != _ALLOWED_UNITS.get(measure.variable_medida):
            continue
        if measure.segmento and measure.segmento not in _ALLOWED_SEGMENTS:
            continue
        if measure.frecuencia_khz is not None and not (
            0 <= measure.frecuencia_khz <= 1000
        ):
            continue
        if not (-1000 <= measure.valor_medida <= 1000):
            continue
        if (measure.variable_medida == "body_fat_percentage"
                and not 0 <= measure.valor_medida <= 100):
            continue
        filtered.append({
            "metric": measure.variable_medida,
            "unit": measure.unidad_medida,
            "segment": measure.segmento,
            "frequency_khz": measure.frecuencia_khz,
            "value": measure.valor_medida,
        })
    if not filtered:
        raise ValueError(
            "No hay mediciones públicas válidas (métrica y unidad compatibles)."
        )
    if len(filtered) > 80:
        raise ValueError("Máximo 80 mediciones por examen de demostración.")
    return filtered


def save_demo_exam(
    report: ConfirmedExam,
    *,
    storage_consent: bool,
    publish_consent: bool,
    anonymous_alias: str,
) -> str:
    """Insert demo-only data WITHOUT OAuth; consent checked on the server."""
    if not anonymous_demo_enabled():
        raise PermissionError("Guardado anónimo de demostración deshabilitado.")
    if storage_consent is not True:
        raise PermissionError("Debes aceptar el almacenamiento antes de guardar.")
    if publish_consent not in (True, False):
        raise ValueError("La decisión de publicación debe ser explícita.")

    # This alias is created randomly per Gradio session. Never hash an ID.
    try:
        alias = UUID(anonymous_alias)
        if alias.version != 4:
            raise ValueError("El alias debe ser aleatorio.")
    except (TypeError, AttributeError, ValueError) as exc:
        raise ValueError("Identificador de sesión inválido.") from exc

    # The list intentionally omits every PII field, source hash and original
    # label from ConfirmedExam even if supplied by an OCR report.
    values = anonymized_measurements(report)
    engine = _demo_database_engine()
    try:
        with engine.begin() as conn:
            record_id = conn.execute(text("""
                SELECT public.hj_submit_demo_report(
                    CAST(:alias AS uuid), CAST(:exam_date AS date),
                    :device, CAST(:measurements AS jsonb), :publish
                )
            """), {
                "alias": str(alias),
                "exam_date": report.timestamp.date().isoformat(),
                "device": report.modelo_inbody or "",
                "measurements": json.dumps(values, ensure_ascii=False),
                "publish": publish_consent,
            }).scalar_one()
        return str(record_id)
    finally:
        engine.dispose()
