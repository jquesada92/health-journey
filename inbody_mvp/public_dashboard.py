"""Lectura pública exclusivamente desde una vista de cohortes aprobadas.

No consulta tablas privadas ni devuelve IDs, identificadores de archivos,
nombre/fecha de nacimiento, edades, timestamp exacto o historiales individuales.
La anonimización formal depende de contexto y riesgo, no solamente de quitar PII.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, text

def _public_database_engine():
    """Use ONLY the read-only public DB role, never the private DATABASE_URL."""
    url = os.getenv("PUBLIC_DATABASE_URL")
    if not url:
        raise RuntimeError("PUBLIC_DATABASE_URL no está configurada.")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if not url.startswith("postgresql+psycopg://") or "sslmode=require" not in url:
        raise RuntimeError("PUBLIC_DATABASE_URL requiere PostgreSQL y TLS.")
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=0)

PUBLIC_METRICS: dict[str, str] = {
    "weight": "Peso",
    "skeletal_muscle_mass": "Masa muscular esquelética",
    "body_fat_mass": "Masa grasa corporal",
    "body_fat_percentage": "Porcentaje de grasa corporal",
    "total_body_water": "Agua corporal total",
    "segmental_lean_mass": "Masa magra segmental",
    "segmental_fat_mass": "Masa grasa segmental",
    "phase_angle": "Ángulo de fase",
}

PUBLIC_COLUMNS = (
    "period_month", "device_group", "variable_medida",
    "unidad_medida", "segmento", "frecuencia_khz",
    "participantes", "valor_promedio",
)


def public_dashboard_enabled() -> bool:
    """Public endpoint is disabled by default, even when Neon is configured."""
    return (
        os.getenv("ENABLE_PUBLIC_DASHBOARD", "").strip().lower() in ("1", "true", "yes")
        and bool(os.getenv("PUBLIC_DATABASE_URL"))
    )


def load_public_monthly_summary(variable: str = "weight", max_rows: int = 120) -> list[dict]:
    """Return only pre-approved, >=5-person monthly cohort aggregates.

    Always read the dedicated SQL view. Do not add a join to hj_persons,
    hj_exams, hj_measurements_long, or a row-level query here.
    """
    if not public_dashboard_enabled():
        return []
    if variable not in PUBLIC_METRICS:
        raise ValueError("La variable solicitada no es pública.")
    max_rows = min(max(int(max_rows), 1), 500)
    engine = _public_database_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT period_month, device_group, variable_medida,
                       unidad_medida, segmento, frecuencia_khz,
                       participantes, valor_promedio
                FROM hj_public_monthly_summary
                WHERE variable_medida = :variable
                ORDER BY period_month, device_group, segmento, frecuencia_khz
                LIMIT :row_limit
            """), {"variable": variable, "row_limit": max_rows}).mappings().all()
        result = []
        for row in rows:
            record = {key: row[key] for key in PUBLIC_COLUMNS}
            if int(record["participantes"]) < 5:
                # Defence in depth, including accidental DB view regression.
                continue
            record["period_month"] = record["period_month"].isoformat()
            record["participantes"] = int(record["participantes"])
            record["valor_promedio"] = float(record["valor_promedio"])
            if record["frecuencia_khz"] is not None:
                record["frecuencia_khz"] = float(record["frecuencia_khz"])
            result.append(record)
        return result
    finally:
        engine.dispose()
