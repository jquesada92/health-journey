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
