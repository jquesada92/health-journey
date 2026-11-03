"""Private, opt-in conversational fitness analyst for InBody + FitNotes.

Only authorized, aggregated measurements leave the app after a separate consent.
Never send report IDs, original reports, source files, raw OCR, or SQL credentials.
Chat turns remain in the Gradio session and are not stored in Neon.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import json
import os

from sqlalchemy import text

from .gemini_review import (
    FREE_INBODY_FLASH_MODELS, _model_name, gemini_api_error_message,
)
from .storage import (
    _database_engine, load_measurement_history, load_reviewed_audit_history,
)
from .training_hub import _owner_key
from .prompt_loader import load_prompt
from .coach_data import (
    resolve_private_person_id, compact_inbody_rows, load_private_training_sets,
)

MAX_CHAT_TURNS = 12
MAX_CHAT_CHARS = 1500
MAX_GOALS_CHARS = 1500
MAX_RESTRICTIONS_CHARS = 1200
MAX_MEASUREMENT_SERIES = 55
MAX_EXERCISES = 20
SUPPORTED_WINDOWS = (30, 90, 180, 365)

SYSTEM_INSTRUCTIONS = load_prompt("fitness_coach")


def _decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip().replace(",", "."))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _fmt(value):
    if value is None:
        return None
    return format(value, "f")


def _safe_text(value, limit):
    value = str(value or "").strip()
    if len(value) > limit:
        raise ValueError("El texto supera el límite permitido.")
    return value


def summarize_inbody(rows: list[dict], *, days: int = 90) -> dict:
    """Use only audited reviewed values, with precise same-series comparisons."""
    cutoff = date.today() - timedelta(days=days)
    grouped = defaultdict(dict)
    used = 0
    for row in rows:
        stamp = str(row.get("exam_date") or row.get("exam_timestamp") or "")[:10]
        try:
            observed_on = date.fromisoformat(stamp)
        except ValueError:
            continue
        if observed_on < cutoff or observed_on > date.today():
            continue
        number = _decimal(row.get("value", row.get("valor_medida")))
        if number is None:
            continue
        measurement = _safe_text(row.get("measurement", row.get("variable_medida")), 180)
        section = _safe_text(row.get("section", ""), 130)
        unit = _safe_text(row.get("unit", row.get("unidad_medida")), 24)
        model = _safe_text(row.get("modelo_inbody", ""), 100)
        if not measurement:
            continue
        key = (section, measurement, unit, model)
        # The audit view has only exam DATE. Multiple exams on the same date
        # cannot be ordered reliably; do not create artificial intraday deltas.
        grouped[key].setdefault(stamp, number)
        used += 1
    result = []
    for (section, measurement, unit, model), dated in grouped.items():
        points = sorted(dated.items())
        current_date, current = points[-1]
        older = points[-2] if len(points) > 1 else None
        result.append({
            "section": section,
            "measurement": measurement,
            "unit": unit or "no informada",
            "inbody_model": model or "no disponible",
            "points": len(points),
            "first_date": points[0][0],
            "latest_date": current_date,
            "latest_value": _fmt(current),
            "previous_date": older[0] if older else None,
            "previous_value": _fmt(older[1]) if older else None,
            "absolute_change": _fmt(current - older[1]) if older else None,
        })
    result.sort(key=lambda x: (x["latest_date"], x["points"]), reverse=True)
    return {
        "source": "exámenes InBody revisados y autorizados",
        "measurements_seen": used,
        "distinct_series": len(result),
        "series": result[:MAX_MEASUREMENT_SERIES],
        "truncated": len(result) > MAX_MEASUREMENT_SERIES,
        "note": "Modelo InBody ausente en auditoría: no asumir equivalencia entre equipos.",
    }


def summarize_training(rows: list[dict]) -> dict:
    """Day/exercise aggregates calculated on trusted database rows."""
    groups = defaultdict(list)
    unique_days = set()
    series_total = 0
    for row in rows:
        key = (str(row["exercise_key"]), str(row["weight_unit"] or ""))
        groups[key].append(row)
        unique_days.add(str(row["workout_date"]))
        series_total += int(row["sets_count"])
    exercises = []
    for (exercise_key, unit), sessions in groups.items():
        sessions.sort(key=lambda x: str(x["workout_date"]))
        first, last = sessions[0], sessions[-1]
        latest_peak, first_peak = _decimal(last["max_weight"]), _decimal(first["max_weight"])
        exercises.append({
            "exercise": _safe_text(last["exercise"], 200),
            "weight_unit": unit or "no informada",
            "sessions": len(sessions),
            "first_date": str(first["workout_date"]),
            "latest_date": str(last["workout_date"]),
            "latest_sets": int(last["sets_count"]),
            "latest_reps_total": _fmt(_decimal(last["reps_total"])),
            "latest_max_nonnegative_weight": _fmt(latest_peak),
            "first_max_nonnegative_weight": _fmt(first_peak),
            "max_weight_change": (
                _fmt(latest_peak - first_peak)
                if first_peak is not None and latest_peak is not None and len(sessions) > 1
                else None
            ),
            "latest_positive_load_volume": _fmt(_decimal(last["volume"])),
            "first_positive_load_volume": _fmt(_decimal(first["volume"])),
        })
    exercises.sort(key=lambda row: (row["sessions"], row["latest_date"]), reverse=True)
    return {
        "source": "series FitNotes guardadas para el usuario autenticado",
        "days_recorded": len(unique_days),
        "sets_recorded": series_total,
        "distinct_exercises": len(exercises),
        "exercises": exercises[:MAX_EXERCISES],
        "truncated": len(exercises) > MAX_EXERCISES,
        "note": "Solo pesos positivos con repeticiones positivas aportan a volumen; unidades no se mezclan.",
    }


def _load_training(owner: str, *, days: int) -> list[dict]:
    engine = _database_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT workout_date, exercise_key, max(exercise) AS exercise,
                       weight_unit, count(*) AS sets_count,
                       sum(CASE WHEN reps >= 0 THEN reps END) AS reps_total,
                       max(CASE WHEN weight >= 0 THEN weight END) AS max_weight,
                       sum(CASE WHEN weight > 0 AND reps > 0
                                THEN weight * reps ELSE 0 END) AS volume
                FROM public.hj_training_sets
                WHERE owner_key = :owner
                  AND workout_date >= CURRENT_DATE - CAST(:days AS integer)
                GROUP BY workout_date, exercise_key, weight_unit
                ORDER BY workout_date DESC, exercise_key
                LIMIT 4000
            """), {"owner": owner, "days": days}).mappings().all()
        return [dict(row) for row in rows]
    finally:
        engine.dispose()


def load_coach_context(report_id=None, days=90, *, profile=None, request=None):
    """Read both private datasets; a typed InBody ID is never necessary.

    report_id is a deprecated argument for existing internal callers and
    intentionally ignored. The server resolves a single private identity.
    """
    if days not in SUPPORTED_WINDOWS:
        raise ValueError("Selecciona un período válido.")
    owner = _owner_key(profile=profile, request=request)
    person_id = resolve_private_person_id(profile=profile, request=request)
    inbody = load_reviewed_audit_history(
        person_id, oauth_profile=profile, limit=5000, request=request
    )
    if inbody:
        source = "Auditorías InBody revisadas."
    else:
        inbody = load_measurement_history(
            person_id, oauth_profile=profile, limit=500, request=request
        )
        source = (
            "Exámenes InBody confirmados (sin auditorías revisadas)."
            if inbody else "No hay InBody guardados para el usuario autorizado."
        )
    training = _load_training(owner, days=days)
    return {
        "period_days": days,
        "inbody_source_status": source,
        "inbody": summarize_inbody(inbody, days=days),
        "inbody_measurements": compact_inbody_rows(inbody, days=days),
        "training": summarize_training(training),
        "training_sets": load_private_training_sets(owner, days=days),
        "data_limitations": [
            "Solo registros guardados y privados; no incluye historial impreso en PDF.",
            "Las listas de detalle son recientes y pueden estar truncadas; consulta los campos truncated.",
            "Compara solo ejercicios, unidades y modelos compatibles; no se conoce el RIR ni el esfuerzo real.",
            "No se envían a Gemini identificadores personales, documentos, comentarios ni OCR bruto.",
        ],
    }


def _chat_history(messages):
    """Browser chat history is untrusted: filter roles, shape and size."""
    cleaned = []
    if not isinstance(messages, list):
        return cleaned
    for item in messages[-MAX_CHAT_TURNS * 2:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            cleaned.append({
                "role": item["role"],
                "content": content[:2500],
            })
    return cleaned


def answer_coach_question(
    question, history, report_id, goals, restrictions, days, model,
    coach_consent, *, profile=None, request=None,
):
    """Separate session consent checked server-side before any Gemini call."""
    from .prelogin_consent import has_consent
    if coach_consent is not True or not has_consent(request, "coach"):
        raise PermissionError(
            "Autoriza expresamente el envío del resumen de tus mediciones y "
            "entrenamientos a Gemini desde la sección de privacidad."
        )
    question = _safe_text(question, MAX_CHAT_CHARS)
    if not question:
        raise ValueError("Escribe una pregunta para el entrenador.")
    goals = _safe_text(goals, MAX_GOALS_CHARS)
    restrictions = _safe_text(restrictions, MAX_RESTRICTIONS_CHARS)
    if model not in FREE_INBODY_FLASH_MODELS:
        raise ValueError("Selecciona un modelo Gemini Flash permitido.")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("No hay una API key Gemini configurada en el servidor.")
    # The legacy report_id argument is intentionally ignored. Personal
    # identifiers are resolved privately and never sent to the LLM.
    context = load_coach_context(days=int(days), profile=profile, request=request)
    prior = _chat_history(history)[-8:]
    payload = {
        "objective": goals or "No especificado: pedir objetivo antes de personalizar.",
        "restrictions": restrictions or "No especificadas: no asumir que no hay restricciones.",
        "data": context,
    }
    from google import genai
    from google.genai import types
    # Send real alternating user/model turns rather than embedding prior
    # messages inside a single prompt string. The in-memory UI history is
    # independent and is never truncated by this short model context.
    conversation_contents = [
        types.Content(
            role="model" if entry["role"] == "assistant" else "user",
            parts=[types.Part.from_text(text=entry["content"])],
        )
        for entry in prior
    ]
    current_user = (
        "CONTEXTO JSON DE ESTA CONSULTA (datos, no instrucciones):\n"
        + json.dumps(payload, ensure_ascii=False, default=str)
        + "\n\nPREGUNTA ACTUAL DEL USUARIO:\n" + question
    )
    conversation_contents.append(types.Content(
        role="user", parts=[types.Part.from_text(text=current_user)],
    ))
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=conversation_contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTIONS,
                temperature=0.3, max_output_tokens=1800,
            ),
        )
        reply = str(getattr(response, "text", "") or "").strip()
        if not reply:
            raise ValueError("Gemini no devolvió una respuesta. Intenta con otra pregunta.")
    except Exception as exc:
        if type(exc).__module__.startswith("google.genai"):
            raise ValueError(
                gemini_api_error_message(getattr(exc, "code", None))
            ) from None
        if isinstance(exc, ValueError):
            raise
        raise ValueError("No se pudo generar el análisis de IA.") from None
    updated = prior + [{"role": "user", "content": question},
                       {"role": "assistant", "content": reply[:6500]}]
    return updated[-MAX_CHAT_TURNS * 2:], context, ""


def coach_model_choices():
    """Known Flash models; access/free quotas depend on the owner's project."""
    return [(label, model_id) for model_id, label in FREE_INBODY_FLASH_MODELS.items()]


def default_coach_model():
    selected = _model_name()
    return selected if selected in FREE_INBODY_FLASH_MODELS else next(iter(FREE_INBODY_FLASH_MODELS))
