"""Audit integrity tests for Gemini review rows."""
from copy import deepcopy

import pandas as pd
import pytest

from inbody_mvp.gemini_review import COLUMNS, validate_review


@pytest.fixture
def extracted():
    row = {
        "exam_datetime": "2025-01-26 14:20:00",
        "filename": "report.jpg",
        "person_id": "0088571257",
        "age": 33,
        "section": "Impedancia",
        "measurement": "Brazo derecho - Frecuencia",
        "value": "8.20",
        "unit": "kHz",
        "original_value": "8.20",
        "was_corrected": False,
        "correction_comment": "",
        "reviewed": False,
    }
    return {"rows": [row]}


def test_reviewed_without_correction_preserves_original(extracted):
    frame = pd.DataFrame(deepcopy(extracted["rows"]), columns=COLUMNS)
    frame.loc[0, "reviewed"] = True
    result = validate_review(frame, extracted)[0]
    assert result["value"] == "8.20"
    assert result["original_value"] == "8.20"
    assert result["was_corrected"] is False


def test_correction_requires_comment(extracted):
    frame = pd.DataFrame(deepcopy(extracted["rows"]), columns=COLUMNS)
    frame.loc[0, "reviewed"] = True
    frame.loc[0, "value"] = "8.02"
    with pytest.raises(ValueError, match="comentario"):
        validate_review(frame, extracted)
    frame.loc[0, "correction_comment"] = "Decimal leído incorrectamente."
    result = validate_review(frame, extracted)[0]
    assert result["was_corrected"] is True
    assert result["original_value"] == "8.20"
    assert result["value"] == "8.02"


def test_unreviewed_row_cannot_be_saved(extracted):
    frame = pd.DataFrame(deepcopy(extracted["rows"]), columns=COLUMNS)
    with pytest.raises(ValueError, match="revisado"):
        validate_review(frame, extracted)


def test_original_evidence_cannot_be_modified(extracted):
    frame = pd.DataFrame(deepcopy(extracted["rows"]), columns=COLUMNS)
    frame.loc[0, "reviewed"] = True
    frame.loc[0, "original_value"] = "8.02"
    with pytest.raises(ValueError, match="originales"):
        validate_review(frame, extracted)
