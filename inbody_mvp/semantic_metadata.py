"""Private semantic metadata for InBody and FitNotes model context.

Only generic dictionary rows are loaded. No personal identifiers or SQL
schema dumps are sent to the model. Authentication/coach consent MUST be
verified by the caller before this function is invoked.
"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .storage import _database_engine

MAX_METRIC_DEFINITIONS = 18
MAX_FIELD_DEFINITIONS = 20
_MAX_DICTIONARY_ROWS = 200


def _safe_string(value, limit: int = 420) -> str:
    return str(value or "").strip()[:limit]


def _lookup_key(label: str) -> str:
    """Match stored aliases without treating related metrics as equivalent."""
    value = unicodedata.normalize("NFKD", str(label or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = " ".join(value.casefold().split())
    # A segmental metric has the same *definition* but is not comparable with
    # a whole-body or other-segment measurement. Its original label remains
    # present in the measurements series, separate from this glossary.
    value = re.sub(
        r"^(?:(?:left|right)\s+(?:arm|leg)|trunk)\s*[-–—]\s*",
        "", value,
    )
    if re.fullmatch(r"impedance\s+at\s+\d+(?:\.\d+)?\s*khz", value):
        value = "impedance"
    return value


def load_coach_semantics(measurement_names: list[str]) -> dict:
    """Load allowlisted, non-personal meaning/units/cautions from Neon.

    The user/session authorization is enforced upstream before reading any
    health records. These dictionaries do not grant access to records.
    Gracefully degrades until migration 009 has been applied.
    """
    names = [str(x)[:180] for x in measurement_names[:_MAX_DICTIONARY_ROWS]]
    requested = {_lookup_key(name) for name in names if name}
    engine = _database_engine()
    try:
        with engine.connect() as connection:
            alias_rows = connection.execute(text("""
                SELECT a.alias_normalized, c.canonical_code,
                       c.display_label_es, c.canonical_unit,
                       c.descripcion_medida, c.comparability_rule,
                       c.interpretation_guidance, c.limitations
                FROM public.hj_measurement_aliases a
                JOIN public.hj_measurement_catalog c
                  ON c.canonical_code = a.canonical_code
                ORDER BY a.alias_normalized
                LIMIT 200
            """)).mappings().all()
            field_rows = connection.execute(text("""
                SELECT source_table, field_name, display_label_es,
                       description_es, unit_hint, interpretation_note
                FROM public.hj_ai_field_dictionary
                WHERE exposed_to_ai IS TRUE
                  AND source_table IN (
                      'hj_audit_reviewed_private', 'hj_measurements',
                      'hj_training_sets', 'hj_measurement_catalog'
                  )
                ORDER BY source_table, field_name
                LIMIT 100
            """)).mappings().all()
    except SQLAlchemyError:
        return {
            "available": False, "metric_definitions": [],
            "field_definitions": [],
            "note": "Diccionario semántico no disponible. No inventar definiciones que falten.",
        }
    finally:
        engine.dispose()

    selected = {}
    for row in alias_rows:
        if _lookup_key(row["alias_normalized"]) not in requested:
            continue
        code = _safe_string(row["canonical_code"], 80)
        if code not in selected:
            selected[code] = {
                "code": code,
                "name": _safe_string(row["display_label_es"], 120),
                "canonical_unit_hint": _safe_string(row["canonical_unit"], 30) or None,
                "meaning": _safe_string(row["descripcion_medida"]),
                "comparability": _safe_string(row["comparability_rule"]),
                "interpretation": _safe_string(row["interpretation_guidance"]),
                "limitations": _safe_string(row["limitations"]),
            }
    metrics = list(selected.values())
    definitions = [{
        "table": _safe_string(row["source_table"], 64),
        "field": _safe_string(row["field_name"], 64),
        "label": _safe_string(row["display_label_es"], 90),
        "meaning": _safe_string(row["description_es"], 180),
        "unit_hint": _safe_string(row["unit_hint"], 64) or None,
        "interpretation": _safe_string(row["interpretation_note"], 180),
    } for row in field_rows[:MAX_FIELD_DEFINITIONS]]
    return {
        "available": True,
        "metric_definitions": metrics[:MAX_METRIC_DEFINITIONS],
        "field_definitions": definitions,
        "truncated": len(metrics) > MAX_METRIC_DEFINITIONS
                     or len(field_rows) > MAX_FIELD_DEFINITIONS,
        "note": (
            "Los metadatos explican términos, no cambian valores ni "
            "constituyen diagnóstico. Comparar solo igual unidad, "
            "segmento, frecuencia y equipo cuando aplique."
        ),
    }
