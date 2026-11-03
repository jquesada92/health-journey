"""Edit/delete malformed InBody candidates without losing provenance."""
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from inbody_mvp.gemini_review import (
    COLUMNS, DISPLAY_COLUMNS, compact_review_table, correct_review_value,
    remove_review_row, validate_review, review_status,
)

APP = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


@pytest.fixture
def sample():
    hdr = {
        "exam_datetime": "2025-01-26 14:20:00",
        "filename": "exam.jpg", "person_id": "00077", "age": 33,
    }
    rows = [
        dict(hdr, section="Segmentos", measurement="Ángulo",
             value="sin lectura", unit="°", original_value="sin lectura",
             was_corrected=False, correction_comment="", reviewed=True),
        dict(hdr, section="Composición", measurement="Peso",
             value="75.20", unit="kg", original_value="75.20",
             was_corrected=False, correction_comment="", reviewed=True),
        dict(hdr, section="Composición", measurement="Agua",
             value="-0.370", unit="L", original_value="-0.370",
             was_corrected=False, correction_comment="", reviewed=True),
    ]
    snapshot = {
        "rows": deepcopy(rows), "header": hdr, "filename": "exam.jpg",
        "sha256": "test-only-sha", "raw_response": '{"measurements":"unmodified"}',
    }
    return snapshot, compact_review_table(pd.DataFrame(rows, columns=COLUMNS))


def test_bad_ai_number_is_editable_without_validating_every_other_row(sample):
    snapshot, frame = sample
    updated = correct_review_value(
        frame, snapshot, 0, "8.20", "Confirmado con la imagen."
    )
    assert updated.loc[0, "value"] == "8.20"
    assert updated.loc[0, "was_corrected"] == True
    assert updated.loc[0, "reviewed"] == True
    assert snapshot["rows"][0]["value"] == "sin lectura"
    assert "Revisión completa" in review_status(updated, snapshot)
    assert validate_review(updated, snapshot)[0]["original_value"] == "sin lectura"


def test_correct_value_keeps_negative_and_trailing_decimal_zeroes(sample):
    snapshot, frame = sample
    updated = correct_review_value(frame, snapshot, 2, "-0.370", "")
    assert updated.loc[2, "value"] == "-0.370"
    assert updated.loc[2, "was_corrected"] == False


@pytest.mark.parametrize("value,reason,message", [
    ("abc", "Corregido", "Valor numérico inválido"),
    ("", "Corregido", "sin valor"),
    ("NaN", "Corregido", "Valor no finito"),
    ("8.20", "", "motivo"),
])
def test_correct_value_fails_with_actionable_error(sample, value, reason, message):
    snapshot, frame = sample
    original = deepcopy(snapshot)
    with pytest.raises(ValueError, match=message):
        correct_review_value(frame, snapshot, 0, value, reason)
    assert snapshot == original


def test_remove_invalid_row_aligns_remaining_originals_and_preserves_source(sample):
    snapshot, frame = sample
    original = deepcopy(snapshot)
    remaining, pruned = remove_review_row(frame, snapshot, 0)
    assert list(remaining.columns) == DISPLAY_COLUMNS
    assert len(remaining) == len(pruned["rows"]) == 2
    assert remaining.iloc[0]["value"] == "75.20"
    assert remaining.iloc[1]["value"] == "-0.370"
    assert pruned["rows"][0]["measurement"] == "Peso"
    assert pruned["raw_response"] == snapshot["raw_response"]
    assert pruned["excluded_review_rows"][0]["original_value"] == "sin lectura"
    assert snapshot == original
    assert len(validate_review(remaining, pruned)) == 2
    assert "Revisión completa" in review_status(remaining, pruned)


def test_remove_middle_row_then_correct_maintains_original_pairing(sample):
    snapshot, frame = sample
    without_weight, pruned = remove_review_row(frame, snapshot, 1)
    changed = correct_review_value(
        without_weight, pruned, 0, "7.50", "Verificado con el PDF"
    )
    saved_rows = validate_review(changed, pruned)
    assert [row["original_measurement"] for row in saved_rows] == ["Ángulo", "Agua"]
    assert saved_rows[0]["original_value"] == "sin lectura"
    assert saved_rows[1]["original_value"] == "-0.370"


def test_deleting_last_row_is_refused(sample):
    snapshot, frame = sample
    frame, snapshot = remove_review_row(frame, snapshot, 0)
    frame, snapshot = remove_review_row(frame, snapshot, 0)
    with pytest.raises(ValueError, match="al menos una medición"):
        remove_review_row(frame, snapshot, 0)


@pytest.mark.parametrize("index", [-1, 3, True, "0", None])
def test_invalid_selection_does_not_mutate_review(sample, index):
    snapshot, frame = sample
    with pytest.raises(ValueError):
        remove_review_row(frame, snapshot, index)
    assert len(snapshot["rows"]) == 3


def test_direct_grid_deletion_or_reordering_cannot_change_audit_alignment(sample):
    snapshot, frame = sample
    with pytest.raises(ValueError, match="Eliminar fila seleccionada"):
        remove_review_row(frame.iloc[1:], snapshot, 0)
    swapped = frame.iloc[[1, 0, 2]].reset_index(drop=True)
    with pytest.raises(ValueError, match="valor original"):
        correct_review_value(swapped, snapshot, 0, "75.30", "Razón")


def test_invalid_number_shows_row_and_measurement_in_review_error(sample):
    snapshot, frame = sample
    status = review_status(frame, snapshot)
    assert "Fila 1" in status
    assert "Ángulo" in status
    assert "Valor numérico inválido" in status


def test_row_editing_and_deletion_are_explicit_and_one_validation_button():
    assert "selected_review_row = gr.State(value=None)" in APP
    assert "gemini_table.select(" in APP
    assert "correct_review_value(" in APP
    assert "remove_review_row(" in APP
    assert "delete_review_row.click(" in APP
    assert "apply_row_correction.click(" in APP
    assert "gemini_review_continue" not in APP
    assert "Continuar a validación" not in APP
    assert APP.count('"Validar revisión"') == 1
    assert "save_audit(" in APP
