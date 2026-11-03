"""InBody exam datetime from the exact 14-digit token after the first '_'.

The filename timestamp is local report time with no inferred timezone.
Never search for unrelated embedded digits or parse the upload time.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

_FILENAME_EXAM = re.compile(r"^[^_]+_([0-9]{14})(?=$|[._-])")


def exam_datetime_from_filename(filename: str) -> str | None:
    """Return 'YYYY-MM-DD HH:MM:SS' or None for legacy filenames.

    A 14-digit token at this *exact* position is authoritative; an
    impossible date or time raises instead of silently trusting OCR.
    No delimiter after the first underscore means no reliable timestamp.
    """
    name = Path(str(filename or "")).name
    match = _FILENAME_EXAM.match(name)
    if not match:
        return None
    token = match.group(1)
    try:
        timestamp = datetime.strptime(token, "%Y%m%d%H%M%S")
        if timestamp.strftime("%Y%m%d%H%M%S") != token:
            raise ValueError("timestamp normalized")
    except ValueError as exc:
        raise ValueError(
            "El nombre del archivo contiene una fecha/hora inválida "
            "después del primer '_'. Usa YYYYMMDDHHMMSS."
        ) from exc
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


_REPORT_DATETIME = re.compile(
    r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})\.?\s+"
    r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$"
)


def normalize_report_exam_datetime(value: str | None) -> str | None:
    """Normalize report-local DD.MM.YYYY HH:MM to canonical SQL datetime.

    InBody often displays a trailing dot after the year, and may omit the
    seconds. It is *not* YYYY.MM.DD. A two-digit year is explicitly
    interpreted as 20YY for contemporary 2000-2099 reports. The original
    text is kept separately in raw Gemini response for traceability.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    matched = _REPORT_DATETIME.fullmatch(raw)
    if matched:
        day, month, year, hour, minute, seconds = matched.groups()
        year_number = int(year)
        if len(year) == 2:
            year_number += 2000
        try:
            parsed = datetime(
                year_number, int(month), int(day),
                int(hour), int(minute), int(seconds or "0"),
            )
        except ValueError as exc:
            raise ValueError(
                "La fecha/hora del reporte es inválida. "
                "Usa DD.MM.AAAA HH:MM."
            ) from exc
    else:
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(
                "Formato de fecha del reporte no reconocido: "
                "usa DD.MM.AAAA HH:MM."
            ) from exc
    if parsed.tzinfo is not None:
        raise ValueError(
            "El reporte no incluye zona horaria; no se debe convertir "
            "automáticamente una fecha con zona."
        )
    return parsed.strftime("%Y-%m-%d %H:%M:%S")
