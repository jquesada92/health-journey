"""FitNotes CSV ingestion and private, idempotent Neon training-log persistence.

FitNotes exports are cumulative. Identical sets in one session are valid:
identity is owner + workout date + normalized exercise + set ordinal, not
the weight/reps tuple. CSV content stays in the Gradio session until consent.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from .app_auth import MASTER_DEMO_USERNAME, master_demo_authenticated, password_login_enabled
from .storage import _database_engine, require_database_access

MAX_CSV_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
COLUMNS = (
    "Date", "Exercise", "Category", "Weight", "Weight Unit",
    "Reps", "Distance", "Distance Unit", "Time", "Comment",
)
PREVIEW_COLUMNS = (
    "Fecha", "Ejercicio", "Categoría", "Serie", "Peso", "Unidad",
    "Reps", "Distancia", "Unidad distancia", "Tiempo (s)", "Comentario",
)
DB_RECORD_COLUMNS = (
    "workout_date date, exercise text, exercise_key text, category text, "
    "set_number integer, weight numeric, weight_unit text, reps numeric, "
    "distance numeric, distance_unit text, duration_seconds integer, "
    "comment text, source_row_number integer"
)
MATCH_CHANGE = (
    "(t.exercise, t.category, t.weight, t.weight_unit, t.reps, "
    "t.distance, t.distance_unit, t.duration_seconds, t.comment) "
    "IS DISTINCT FROM "
    "(i.exercise, i.category, i.weight, i.weight_unit, i.reps, "
    "i.distance, i.distance_unit, i.duration_seconds, i.comment)"
)


def _optional(raw: str | None, maximum: int) -> str | None:
    value = str(raw or "").strip()
    if len(value) > maximum:
        raise ValueError(f"Texto superior a {maximum} caracteres.")
    return value or None


def _number(raw: str | None, field: str, row: int) -> str | None:
    value = _optional(raw, 80)
    if value is None:
        return None
    try:
        number = Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Fila {row}: {field} no es numérico.") from exc
    if not number.is_finite() or abs(number) > Decimal("99999999"):
        raise ValueError(f"Fila {row}: {field} fuera de rango.")
    # Preserve scale from the export; 8.20 must not become 8.
    return str(number)


def _duration(raw: str | None, row: int) -> int | None:
    value = _optional(raw, 32)
    if value is None:
        return None
    parts = value.split(":")
    if len(parts) not in (2, 3) or any(not p.isdigit() for p in parts):
        raise ValueError(f"Fila {row}: duración inválida: usa H:MM:SS.")
    numbers = [int(part) for part in parts]
    hours, minutes, seconds = (
        (0, numbers[0], numbers[1]) if len(numbers) == 2
        else (numbers[0], numbers[1], numbers[2])
    )
    if minutes >= 60 or seconds >= 60 or hours > 9999:
        raise ValueError(f"Fila {row}: duración fuera de rango.")
    return hours * 3600 + minutes * 60 + seconds


def parse_fitnotes_bytes(raw: bytes, filename: str = "fitnotes.csv") -> dict:
    """Parse every set without dropping repeated sets or rounding decimals."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_CSV_BYTES:
        raise ValueError("El CSV está vacío o supera el límite de 10 MB.")
    name = Path(str(filename)).name
    if not name.lower().endswith(".csv") or len(name) > 255:
        raise ValueError("Selecciona un archivo FitNotes .csv válido.")
    if b"\x00" in raw:
        raise ValueError("El archivo no es un CSV de texto.")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("FitNotes debe exportarse como CSV UTF-8.") from exc
    reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
    if reader.fieldnames is None or tuple(reader.fieldnames) != COLUMNS:
        raise ValueError("Encabezado de FitNotes incorrecto: se esperan las 10 columnas originales.")
    output = []
    sequence = defaultdict(int)
    days = set()
    exercises = set()
    for source_number, values in enumerate(reader, start=2):
        if source_number > MAX_ROWS + 1:
            raise ValueError("El CSV supera 100.000 series.")
        if None in values:
            raise ValueError(f"Fila {source_number}: columnas adicionales no esperadas.")
        date_str = (values["Date"] or "").strip()
        try:
            workout_date = date.fromisoformat(date_str)
        except ValueError as exc:
            raise ValueError(f"Fila {source_number}: fecha inválida.") from exc
        if workout_date.year < 1900 or workout_date.year > 2100:
            raise ValueError(f"Fila {source_number}: fecha fuera de rango.")
        exercise = _optional(values["Exercise"], 200)
        if not exercise:
            raise ValueError(f"Fila {source_number}: falta el ejercicio.")
        exercise_key = re.sub(r"\s+", " ", exercise).casefold()
        key = (date_str, exercise_key)
        sequence[key] += 1
        record = {
            "workout_date": workout_date.isoformat(),
            "exercise": exercise,
            "exercise_key": exercise_key,
            "category": _optional(values["Category"], 100),
            "set_number": sequence[key],
            "weight": _number(values["Weight"], "peso", source_number),
            "weight_unit": _optional(values["Weight Unit"], 24),
            "reps": _number(values["Reps"], "repeticiones", source_number),
            "distance": _number(values["Distance"], "distancia", source_number),
            "distance_unit": _optional(values["Distance Unit"], 24),
            "duration_seconds": _duration(values["Time"], source_number),
            "comment": _optional(values["Comment"], 2000),
            "source_row_number": source_number,
        }
        output.append(record)
        days.add(date_str)
        exercises.add(exercise_key)
    if not output:
        raise ValueError("El CSV no contiene series.")
    return {
        "filename": name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "rows": output,
        "days": len(days),
        "exercises": len(exercises),
        "first_date": min(days),
        "last_date": max(days),
    }


def preview_training(payload: dict, limit: int = 60) -> pd.DataFrame:
    records = []
    for r in payload["rows"][:limit]:
        records.append([
            r["workout_date"], r["exercise"], r["category"] or "",
            r["set_number"], r["weight"] or "", r["weight_unit"] or "",
            r["reps"] or "", r["distance"] or "", r["distance_unit"] or "",
            "" if r["duration_seconds"] is None else str(r["duration_seconds"]),
            r["comment"] or "",
        ])
    return pd.DataFrame(records, columns=PREVIEW_COLUMNS)


def inspect_fitnotes_upload(file_path: str):
    if not file_path:
        raise ValueError("Selecciona un CSV de FitNotes.")
    path = Path(file_path)
    if not path.is_file() or path.stat().st_size > MAX_CSV_BYTES:
        raise ValueError("No se pudo recibir el CSV o supera 10 MB.")
    payload = parse_fitnotes_bytes(path.read_bytes(), path.name)
    status = (
        f"**{len(payload['rows']):,} series** · "
        f"{payload['days']} días · {payload['exercises']} ejercicios. "
        f"Desde {payload['first_date']} hasta {payload['last_date']}. "
        "Vista previa de las primeras 60 filas. Aún no se ha guardado nada."
    )
    return payload, status, preview_training(payload)


def _owner_key(profile=None, request=None) -> str:
    require_database_access(profile, request=request)
    if master_demo_authenticated(request):
        return "app:" + MASTER_DEMO_USERNAME
    username = getattr(profile, "username", None)
    if isinstance(username, str) and username.strip():
        return "hf:" + username.strip().casefold()
    if os.getenv("SPACE_ID") or password_login_enabled():
        raise PermissionError("Necesitas iniciar sesión para guardar entrenamientos.")
    # Only for a developer-run instance with no hosted Space.
    return "local:single-user"


def _database_payload(payload: dict) -> tuple[str, list[dict]]:
    if not isinstance(payload, dict):
        raise ValueError("Primero carga y valida el CSV.")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not (1 <= len(rows) <= MAX_ROWS):
        raise ValueError("La sesión no contiene series válidas.")
    digest = payload.get("source_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("No se pudo verificar la huella del CSV.")
    return digest, rows


def _compare_existing(connection, owner: str, rows_json: str) -> tuple[int, int]:
    result = connection.execute(text(f"""
        SELECT count(*)::integer AS existing,
               count(*) FILTER (WHERE {MATCH_CHANGE})::integer AS changed
        FROM jsonb_to_recordset(CAST(:rows_json AS jsonb))
            AS i({DB_RECORD_COLUMNS})
        JOIN public.hj_training_sets t
          ON t.owner_key = :owner
         AND t.workout_date = i.workout_date
         AND t.exercise_key = i.exercise_key
         AND t.set_number = i.set_number
    """), {"rows_json": rows_json, "owner": owner}).mappings().one()
    return int(result["existing"]), int(result["changed"])


def save_training_import(
    payload: dict, consent: bool, overwrite: bool = False,
    profile=None, request=None,
) -> str:
    if consent is not True:
        raise ValueError("Marca la autorización para almacenar tu entrenamiento en Neon.")
    owner = _owner_key(profile, request)
    digest, rows = _database_payload(payload)
    filename = str(payload.get("filename") or "fitnotes.csv")
    if len(filename) > 255:
        raise ValueError("Nombre de archivo demasiado largo.")
    rows_json = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    engine = _database_engine()
    try:
        with engine.begin() as conn:
            # Serialize imports per owner to ensure reliable conflict counting.
            conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:owner, 0))"),
                {"owner": owner},
            )
            previous = conn.execute(text("""
                SELECT 1 FROM public.hj_training_imports
                WHERE owner_key = :owner AND source_sha256 = :digest
            """), {"owner": owner, "digest": digest}).scalar_one_or_none()
            if previous:
                return "Este archivo ya fue importado. No se duplicó ninguna serie."
            existing, changed = _compare_existing(conn, owner, rows_json)
            if changed and not overwrite:
                raise ValueError(
                    f"Hay {changed} series previamente guardadas con datos distintos. "
                    "Revisa el CSV y marca la confirmación de sobrescritura "
                    "si deseas reemplazar esas series."
                )
            new_count = len(rows) - existing
            import_id = conn.execute(text("""
                INSERT INTO public.hj_training_imports
                    (owner_key, source_sha256, filename, row_count,
                     inserted_count, updated_count)
                VALUES (:owner, :digest, :filename, :count, :inserted, :updated)
                RETURNING import_id
            """), {
                "owner": owner, "digest": digest, "filename": filename,
                "count": len(rows), "inserted": new_count,
                "updated": changed if overwrite else 0,
            }).scalar_one()
            conn.execute(text(f"""
                INSERT INTO public.hj_training_sets
                    (owner_key, workout_date, exercise, exercise_key, category,
                     set_number, weight, weight_unit, reps, distance,
                     distance_unit, duration_seconds, comment,
                     first_import_id, last_import_id,
                     first_row_number, last_row_number)
                SELECT :owner, i.workout_date, i.exercise, i.exercise_key,
                       i.category, i.set_number, i.weight, i.weight_unit,
                       i.reps, i.distance, i.distance_unit, i.duration_seconds,
                       i.comment, :import_id, :import_id,
                       i.source_row_number, i.source_row_number
                FROM jsonb_to_recordset(CAST(:rows_json AS jsonb))
                    AS i({DB_RECORD_COLUMNS})
                ON CONFLICT (owner_key, workout_date, exercise_key, set_number)
                DO UPDATE SET
                    exercise = EXCLUDED.exercise,
                    category = EXCLUDED.category,
                    weight = EXCLUDED.weight,
                    weight_unit = EXCLUDED.weight_unit,
                    reps = EXCLUDED.reps,
                    distance = EXCLUDED.distance,
                    distance_unit = EXCLUDED.distance_unit,
                    duration_seconds = EXCLUDED.duration_seconds,
                    comment = EXCLUDED.comment,
                    last_import_id = EXCLUDED.last_import_id,
                    last_row_number = EXCLUDED.last_row_number,
                    updated_at = now()
                WHERE :allow_overwrite AND
                    ((hj_training_sets.exercise, hj_training_sets.category,
                      hj_training_sets.weight, hj_training_sets.weight_unit,
                      hj_training_sets.reps, hj_training_sets.distance,
                      hj_training_sets.distance_unit, hj_training_sets.duration_seconds,
                      hj_training_sets.comment)
                    IS DISTINCT FROM
                     (EXCLUDED.exercise, EXCLUDED.category, EXCLUDED.weight,
                      EXCLUDED.weight_unit, EXCLUDED.reps, EXCLUDED.distance,
                      EXCLUDED.distance_unit, EXCLUDED.duration_seconds,
                      EXCLUDED.comment))
            """), {
                "owner": owner, "rows_json": rows_json,
                "import_id": import_id, "allow_overwrite": bool(overwrite),
            })
        return (
            f"Guardado en Neon: {new_count} series nuevas, "
            f"{changed if overwrite else 0} actualizadas y "
            f"{existing - changed} ya existentes sin cambios."
        )
    finally:
        engine.dispose()


def recent_training(profile=None, request=None, limit: int = 60) -> pd.DataFrame:
    owner = _owner_key(profile, request)
    limit = max(1, min(int(limit), 200))
    engine = _database_engine()
    try:
        with engine.connect() as conn:
            records = conn.execute(text("""
                SELECT workout_date AS "Fecha", exercise AS "Ejercicio",
                       category AS "Categoría", set_number AS "Serie",
                       weight AS "Peso", weight_unit AS "Unidad",
                       reps AS "Reps", distance AS "Distancia",
                       distance_unit AS "Unidad distancia",
                       duration_seconds AS "Tiempo (s)", comment AS "Comentario"
                FROM public.hj_training_sets
                WHERE owner_key = :owner
                ORDER BY workout_date DESC, exercise, set_number
                LIMIT :limit
            """), {"owner": owner, "limit": limit}).mappings().all()
        return pd.DataFrame([dict(row) for row in records], columns=PREVIEW_COLUMNS)
    finally:
        engine.dispose()
