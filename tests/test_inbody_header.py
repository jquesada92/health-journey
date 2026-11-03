"""Single editable InBody exam header, compact grid and original audit evidence."""
from copy import deepcopy

import pandas as pd
import pytest

from inbody_mvp.gemini_review import (
    COLUMNS, DISPLAY_COLUMNS, compact_review_table, header_for_review,
    validate_review, review_status,
)


@pytest.fixture
def sample():
    header = {
        "exam_datetime": "2025-01-26 14:20:00",
        "filename": "report.jpg",
        "person_id": "0088571257",
        "age": 33,
    }
    rows = []
    for name, value, unit in (
        ("Total Body Water", "8.20", "L"),
        ("Weight", "-0.370", "kg"),
    ):
        rows.append({
            **header, "section": "Body Composition Analysis",
            "measurement": name, "value": value, "unit": unit,
            "original_value": value, "was_corrected": False,
            "correction_comment": "", "reviewed": True,
        })
    return {
        "rows": deepcopy(rows), "header": deepcopy(header),
        "filename": "report.jpg", "raw_response": '{"source":"unchanged"}',
    }, pd.DataFrame(rows, columns=COLUMNS)


def test_general_metadata_is_not_repeated_as_grid_columns(sample):
    snapshot, original_frame = sample
    displayed = compact_review_table(original_frame)
    assert list(displayed.columns) == DISPLAY_COLUMNS
    assert set(["exam_datetime", "filename", "person_id", "age"]).isdisjoint(displayed.columns)
    assert displayed.iloc[0]["value"] == "8.20"
    assert displayed.iloc[1]["value"] == "-0.370"
    assert header_for_review(snapshot) == (
        "2025-01-26 14:20:00", "report.jpg", "0088571257", "33", "",
    )
    assert header_for_review(None) == ("", "", "", "", "")


def test_correction_is_applied_once_to_every_row_and_original_is_unchanged(sample):
    snapshot, frame = sample
    original = deepcopy(snapshot)
    edits = {
        "exam_datetime": "2026-03-03 18:41:00",
        "filename": "report.jpg",
        "person_id": "000101",
        "age": "34",
        "correction_comment": "Encabezado leído incorrectamente.",
    }
    verified = validate_review(compact_review_table(frame), snapshot, edits)
    assert len(verified) == 2
    assert {row["exam_datetime"] for row in verified} == {"2026-03-03 18:41:00"}
    assert {row["person_id"] for row in verified} == {"000101"}
    assert {row["age"] for row in verified} == {34}
    assert all(row["filename"] == "report.jpg" for row in verified)
    assert all("Encabezado leído incorrectamente." in row["correction_comment"]
               for row in verified)
    assert all(row["was_corrected"] is False for row in verified)
    assert [row["original_value"] for row in verified] == ["8.20", "-0.370"]
    assert snapshot == original


def test_measurement_and_header_edits_have_separate_audit_semantics(sample):
    snapshot, frame = sample
    compact = compact_review_table(frame)
    compact.loc[0, "value"] = "8.02"
    compact.loc[0, "correction_comment"] = "Decimal 8.02 verificado."
    edits = {
        "exam_datetime": "2025-01-26 14:20:00",
        "filename": "report.jpg",
        "person_id": "0088571257",
        "age": "34",
        "correction_comment": "Edad corregida.",
    }
    rows = validate_review(compact, snapshot, edits)
    assert rows[0]["was_corrected"] is True
    assert rows[1]["was_corrected"] is False
    assert "Decimal 8.02 verificado." in rows[0]["correction_comment"]
    assert all("Edad corregida." in row["correction_comment"] for row in rows)
    assert "encabezado corregido" in review_status(compact, snapshot, edits)


@pytest.mark.parametrize("changed", [
    {"person_id": "00001"}, {"exam_datetime": "2025-01-27 01:01:01"},
    {"age": "34"},
])
def test_header_edits_require_one_reason(sample, changed):
    snapshot, frame = sample
    edits = dict(zip(
        ("exam_datetime", "filename", "person_id", "age", "correction_comment"),
        header_for_review(snapshot),
    ))
    edits.update(changed)
    with pytest.raises(ValueError, match="motivo de la corrección"):
        validate_review(compact_review_table(frame), snapshot, edits)


@pytest.mark.parametrize("changes,reason", [
    ({"exam_datetime": "2026-02-30 14:20:00"}, "Fecha/hora inválida"),
    ({"exam_datetime": "2025-01-26"}, "Fecha/hora inválida"),
    ({"person_id": ""}, "ID de persona"),
    ({"age": "34.5"}, "número entero"),
    ({"age": "121"}, "entre 0 y 120"),
    ({"filename": "swapped-report.jpg"}, "no puede modificarse"),
])
def test_invalid_header_data_is_rejected_before_save(sample, changes, reason):
    snapshot, frame = sample
    edits = dict(zip(
        ("exam_datetime", "filename", "person_id", "age", "correction_comment"),
        header_for_review(snapshot),
    ))
    edits["correction_comment"] = "Corrección confirmada."
    edits.update(changes)
    with pytest.raises(ValueError, match=reason):
        validate_review(compact_review_table(frame), snapshot, edits)


def test_measurement_review_still_required_when_header_is_correct(sample):
    snapshot, frame = sample
    table = compact_review_table(frame)
    table.loc[1, "reviewed"] = False
    edits = dict(zip(
        ("exam_datetime", "filename", "person_id", "age", "correction_comment"),
        header_for_review(snapshot),
    ))
    with pytest.raises(ValueError, match="revisado"):
        validate_review(table, snapshot, edits)


def test_legacy_full_width_cannot_change_original_provenance(sample):
    snapshot, frame = sample
    frame.loc[0, "person_id"] = "forged"
    with pytest.raises(ValueError, match="datos originales"):
        validate_review(frame, snapshot)
