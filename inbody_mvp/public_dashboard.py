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


def public_mode_requested() -> bool:
    """Check the public-only mode independently of DB configuration."""
    return os.getenv("ENABLE_PUBLIC_DASHBOARD", "").strip().lower() in (
        "1", "true", "yes"
    )


def public_dashboard_enabled() -> bool:
    """Public endpoint is disabled by default, even when Neon is configured."""
    return public_mode_requested() and bool(os.getenv("PUBLIC_DATABASE_URL"))


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



# Public personal history is opt-in per exam. The random alias is generated
# inside PostgreSQL and is NOT a hash of the real InBody identifier.
PUBLIC_SERIES_COLUMNS = (
    "anonymous_id", "exam_date", "device_group", "variable_medida",
    "unidad_medida", "segmento", "frecuencia_khz", "valor_medida",
)


def load_public_person_series(
    variable: str = "weight", max_rows: int = 500,
) -> list[dict]:
    """Fetch only approved, pseudonymous individual measurements.

    A UUID alias and date-only granularity reduce direct identification,
    but personal measurement patterns can still be re-identifiable.
    """
    if not public_dashboard_enabled():
        return []
    if variable not in PUBLIC_METRICS:
        raise ValueError("La variable solicitada no está aprobada para publicación.")
    limit = min(max(int(max_rows), 1), 1500)
    # Demo view is isolated from production tables and can only be read by
    # the public read-only role. No anonymous callback can query patient data.
    if os.getenv("ENABLE_ANONYMOUS_DEMO", "").strip().lower() in ("1", "true", "yes"):
        source_sql = """
            SELECT anonymous_id, exam_date, device_group, variable_medida,
                   unidad_medida, segmento, frecuencia_khz, valor_medida
            FROM hj_public_person_series
            UNION ALL
            SELECT anonymous_id, exam_date, device_group, variable_medida,
                   unidad_medida, segmento, frecuencia_khz, valor_medida
            FROM hj_demo_public_series
        """
    else:
        source_sql = """
            SELECT anonymous_id, exam_date, device_group, variable_medida,
                   unidad_medida, segmento, frecuencia_khz, valor_medida
            FROM hj_public_person_series
        """
    engine = _public_database_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT anonymous_id, exam_date, device_group, variable_medida,
                       unidad_medida, segmento, frecuencia_khz, valor_medida
                FROM (
            """ + source_sql + """
                ) AS published
                WHERE variable_medida = :metric
                ORDER BY exam_date, anonymous_id
                LIMIT :row_limit
            """), {"metric": variable, "row_limit": limit}).mappings().all()
        answer = []
        for row in rows:
            record = {key: row[key] for key in PUBLIC_SERIES_COLUMNS}
            if record["exam_date"] is None or record["valor_medida"] is None:
                continue
            record["anonymous_id"] = str(record["anonymous_id"])
            record["exam_date"] = record["exam_date"].isoformat()
            record["valor_medida"] = float(record["valor_medida"])
            if record["frecuencia_khz"] is not None:
                record["frecuencia_khz"] = float(record["frecuencia_khz"])
            answer.append(record)
        return answer
    finally:
        engine.dispose()
