"""Classify report language from layout headings; never infer from patient identity.

Supported values are ES, EN, UNKNOWN. Uncertain reports stay UNKNOWN for review.
This classification is independent of the machine model and measurement codes.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

ReportLanguage = Literal["ES", "EN", "UNKNOWN"]

_SPANISH = (
    r"analisis de (?:la )?composicion corporal",
    r"analisis (?:musculo[ -]grasa|de grasa segmental|de magro por segmentos)",
    r"analisis de obesidad",
    r"historial de composicion corporal",
    r"parametros de investigacion",
    r"porcentaje de grasa corporal",
    r"masa grasa corporal",
    r"masa muscular esqueletica",
    r"relacion cintura[ -]cadera",
    r"puntuacion inbody",
    r"fecha\s*/\s*hora del test",
    r"agua corporal total",
)
_ENGLISH = (
    r"body composition analysis",
    r"muscle[ -]fat analysis",
    r"obesity analysis",
    r"segmental lean analysis",
    r"segmental fat analysis",
    r"body composition history",
    r"research parameters",
    r"percent(?:age)? body fat",
    r"skeletal muscle mass",
    r"waist[ -]hip ratio",
    r"inbody score",
    r"test date\s*/\s*time",
    r"total body water",
)


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def detect_report_language(text: str) -> ReportLanguage:
    """Require >=2 independent section/metric anchors and a clear winner.

    One-word matches and short lines intentionally remain UNKNOWN.
    """
    source = re.sub(r"\s+", " ", _fold(text or ""))
    es = sum(bool(re.search(pattern, source)) for pattern in _SPANISH)
    en = sum(bool(re.search(pattern, source)) for pattern in _ENGLISH)
    if es >= 2 and es > en:
        return "ES"
    if en >= 2 and en > es:
        return "EN"
    return "UNKNOWN"
