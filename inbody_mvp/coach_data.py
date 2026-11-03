"""Read-only, single-person InBody and FitNotes evidence for fitness coaching.

Server-authorized identity is resolved privately, never received from a chat
field or included in a Gemini payload. No database work happens on import.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import os

from sqlalchemy import text

from .storage import _database_engine, require_database_access

MAX_INBODY_DETAIL = 160
MAX_TRAINING_DETAIL = 180


def _numeric(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return format(number, "f") if number.is_finite() else None


def _label(value, maximum=200):
    return str(value or "").strip()[:maximum]


def resolve_private_person_id(*, profile=None, request=None) -> str:
    """Resolve only one InBody subject with private authorization.

    Prefer a Space Secret, and support the existing private dashboard alias.
    Otherwise discover an ID only when all records identify one person.
    Refuse to infer a person when multiple identities are present.
    """
    require_database_access(oauth_profile=profile, request=request)
    configured = (
        os.getenv("COACH_PERSON_ID", "").strip()
        or os.getenv("DASHBOARD_TEST_PERSON_ID", "").strip()
    )
    if configured:
        return configured
    engine = _database_engine()
    try:
        with engine.connect() as connection:
            people = connection.execute(text("""
                SELECT DISTINCT person_id
                FROM (
                    SELECT normalized_person_id AS person_id
                    FROM public.hj_person_aliases
                    UNION ALL
                    SELECT CASE WHEN id_persona ~ '^[0-9 -]+$'
                                THEN regexp_replace(id_persona, '[^0-9]', '', 'g')
                                ELSE upper(trim(id_persona))
                           END AS person_id
                    FROM public.hj_persons
                ) stored
                WHERE person_id IS NOT NULL AND person_id <> ''
                ORDER BY person_id
                LIMIT 2
            """)).scalars().all()
    finally:
        engine.dispose()
    if len(people) != 1:
        raise PermissionError(
            "No se pudo identificar un único historial InBody privado. "
            "Configura COACH_PERSON_ID como Secret del Space."
        )
    return str(people[0])


def compact_inbody_rows(rows: list[dict], *, days: int) -> dict:
    """Bounded recent measurement observations, no identity or document."""
    today = date.today()
    cutoff = today - timedelta(days=days)
    observations = []
    for row in rows:
        stamp = str(row.get("exam_date") or row.get("exam_timestamp") or "")[:10]
        try:
            observed = date.fromisoformat(stamp)
        except ValueError:
            continue
        if observed > today or observed < cutoff:
            continue
        value = _numeric(row.get("value", row.get("valor_medida")))
        name = _label(row.get("measurement", row.get("variable_medida")), 180)
        if value is None or not name:
            continue
        observations.append({
            "date": stamp,
            "measurement": name,
            "section": _label(row.get("section"), 130),
            "value": value,
            "unit": _label(row.get("unit", row.get("unidad_medida")), 24),
            "model": _label(row.get("modelo_inbody"), 100) or None,
        })
    observations.sort(key=lambda r: (r["date"], r["measurement"]), reverse=True)
    return {
        "measurements_available": len(observations),
        "measurements": observations[:MAX_INBODY_DETAIL],
        "truncated": len(observations) > MAX_INBODY_DETAIL,
    }


def load_private_training_sets(owner: str, *, days: int) -> dict:
    """Read real FitNotes series, bounded and filtered by authorized owner.

    The aggregation in ai_coach remains independent; this list gives
    Gemini date, exercise, individual set load, repetitions and duration.
    """
    engine = _database_engine()
    try:
        with engine.connect() as connection:
            records = connection.execute(text("""
                SELECT workout_date, exercise, category, set_number,
                       weight, weight_unit, reps, distance,
                       distance_unit, duration_seconds
                FROM public.hj_training_sets
                WHERE owner_key = :owner
                  AND workout_date >= CURRENT_DATE - CAST(:days AS integer)
                ORDER BY workout_date DESC, exercise_key, set_number
                LIMIT :row_limit
            """), {
                "owner": owner, "days": days,
                "row_limit": MAX_TRAINING_DETAIL + 1,
            }).mappings().all()
    finally:
        engine.dispose()
    sets = [{
        "date": str(row["workout_date"]),
        "exercise": _label(row["exercise"]),
        "category": _label(row.get("category"), 100) or None,
        "set": int(row["set_number"]),
        "weight": _numeric(row.get("weight")),
        "weight_unit": _label(row.get("weight_unit"), 24) or None,
        "reps": _numeric(row.get("reps")),
        "distance": _numeric(row.get("distance")),
        "distance_unit": _label(row.get("distance_unit"), 24) or None,
        "duration_seconds": row.get("duration_seconds"),
    } for row in records[:MAX_TRAINING_DETAIL]]
    return {
        "sets": sets,
        "truncated": len(records) > MAX_TRAINING_DETAIL,
        "note": "Series recientes; usar el resumen de FitNotes para tendencias globales.",
    }
