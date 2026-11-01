"""Isolated, no-login classroom demo persistence.

Stores only selected numeric metrics, a random UUID alias, date-only and a
sanitized device group. NEVER stores the report ID, name, age, OCR, source
hash or uploaded bytes. Uses its own restricted SQL role/function.
"""
from __future__ import annotations

import json
import os
import re
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

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
        base_metric = measure.variable_medida.split("__", 1)[0]
        if base_metric not in PUBLIC_METRICS:
            continue
        if measure.unidad_medida != _ALLOWED_UNITS.get(base_metric):
            continue
        if measure.segmento and measure.segmento not in _ALLOWED_SEGMENTS:
            continue
        if not (-1000 <= measure.valor_medida <= 1000):
            continue
        if (base_metric == "body_fat_percentage"
                and not 0 <= measure.valor_medida <= 100):
            continue
        suffix = measure.variable_medida.rsplit("__", 1)[-1]
        frequency = None
        if suffix.endswith("khz"):
            try:
                frequency = float(suffix[:-3])
            except ValueError:
                continue
            if not 0 <= frequency <= 1000:
                continue
        filtered.append({
            "metric": base_metric,
            "unit": measure.unidad_medida,
            "segment": measure.segmento,
            "frequency_khz": frequency,
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
                "device": (report.modelo_inbody if report.modelo_inbody and
                           re.fullmatch(r"InBody [0-9]{2,4}", report.modelo_inbody)
                           else "Modelo no especificado"),
                "measurements": json.dumps(values, ensure_ascii=False),
                "publish": publish_consent,
            }).scalar_one()
        return str(record_id)
    except SQLAlchemyError as exc:
        # Never show database URLs, SQL driver errors or user inputs in Gradio.
        raise RuntimeError(
            "No se pudo guardar el examen de demostración en Neon. "
            "Comprueba la migración 004 y el rol de escritura restringido."
        ) from exc
    finally:
        engine.dispose()
