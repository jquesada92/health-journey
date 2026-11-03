"""Edit/delete malformed InBody candidates without losing provenance."""
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from inbody_mvp.gemini_review import (
    COLUMNS, DISPLAY_COLUMNS, compact_review_table, correct_review_value,
    remove_review_row, reconcile_native_review_rows, sync_review_corrections,
    validate_review, review_status,
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


def test_inline_edits_native_deletions_and_single_save_button():
    assert "selected_review_row = gr.State(value=None)" not in APP
    assert "gemini_table.select(" not in APP
    assert "reconcile_native_review_rows(" in APP
    assert "delete_review_row.click(" not in APP
    assert "gemini_table.input(" in APP
    assert "gemini_table.edit(" not in APP
    assert "row_limits=(1, None)" not in APP
    # Minimum row count is enforced by save_audit, not unsupported Gradio row_limits.
    assert "show_row_numbers=True" in APP
    assert "apply_row_correction.click(" not in APP
    assert 'static_columns=[4]' in APP
    assert 'fn=sync_inline_table_edit' in APP
    assert 'gemini_save = gr.Button(' in APP
    assert 'fn=save_review_and_clear' in APP
    assert 'gemini_check = gr.Button(' not in APP
    assert 'gemini_check.click(' not in APP
    assert '"Guardar cambios"' not in APP
    assert 'fn=progress_after_validation' not in APP
    assert 'table, snapshot = reconcile_native_review_rows(table, snapshot)' in APP
    assert "row_corrected_value" not in APP
    assert "row_correction_reason" not in APP
    assert "gemini_review_continue" not in APP
    assert "Continuar a validación" not in APP
    assert 'save_audit(' in APP


def test_in_table_value_edit_auto_checks_was_corrected(sample):
    snapshot, original = sample
    table = original.copy()
    table.at[1, "value"] = "75.30"
    assert table.at[1, "was_corrected"] == False
    normalized = sync_review_corrections(table, snapshot)
    assert normalized.at[1, "was_corrected"] == True
    assert normalized.at[1, "value"] == "75.30"
    assert normalized.at[1, "original_value"] == "75.20"
    assert original.at[1, "was_corrected"] == False
    assert snapshot["rows"][1]["value"] == "75.20"


def test_mismatched_flag_cannot_hide_a_real_change(sample):
    snapshot, frame = sample
    frame.at[1, "value"] = "80.20"
    frame.at[1, "was_corrected"] = False
    normalized = sync_review_corrections(frame, snapshot)
    assert normalized.at[1, "was_corrected"] == True
    normalized.at[1, "correction_comment"] = "Confirmado en reporte."
    rows = validate_review(normalized, snapshot)
    assert rows[1]["was_corrected"] is True
    assert rows[1]["value"] == "80.20"


def test_restoring_original_value_unchecks_flag(sample):
    snapshot, frame = sample
    frame.at[1, "was_corrected"] = True
    restored = sync_review_corrections(frame, snapshot)
    assert restored.at[1, "was_corrected"] == False
    frame.at[1, "value"] = "77.0"
    updated = sync_review_corrections(frame, snapshot)
    assert updated.at[1, "was_corrected"] == True
    updated.at[1, "value"] = "75.20"
    assert sync_review_corrections(updated, snapshot).at[1, "was_corrected"] == False


def test_inline_edits_keep_negative_and_trailing_zeroes(sample):
    snapshot, frame = sample
    frame.at[2, "value"] = "-0.3700"
    updated = sync_review_corrections(frame, snapshot)
    assert updated.at[2, "value"] == "-0.3700"
    assert updated.at[2, "was_corrected"] == True
    updated.at[2, "correction_comment"] = "Revisé el número."
    assert validate_review(updated, snapshot)[2]["value"] == "-0.3700"


def test_edited_non_numeric_value_may_be_fixed_before_save(sample):
    snapshot, frame = sample
    pending = sync_review_corrections(frame, snapshot)
    assert pending.at[0, "value"] == "sin lectura"
    pending.at[0, "value"] = "8.20"
    ready = sync_review_corrections(pending, snapshot)
    assert ready.at[0, "was_corrected"] == True
    assert "Fila 1" in review_status(ready, snapshot)
    ready.at[0, "correction_comment"] = "Confirmado con el PDF."
    assert len(validate_review(ready, snapshot)) == 3


def test_manual_checkbox_update_is_reconciled_without_source_changes(sample):
    snapshot, frame = sample
    frame.at[1, "was_corrected"] = True
    assert sync_review_corrections(frame, snapshot).at[1, "was_corrected"] == False
    frame.at[1, "unit"] = "lb"
    assert sync_review_corrections(frame, snapshot).at[1, "was_corrected"] == True


def test_delete_after_inline_edit_keeps_correction_and_alignment(sample):
    snapshot, frame = sample
    frame.at[2, "value"] = "-0.375"
    normalized = sync_review_corrections(frame, snapshot)
    pruned, new_snapshot = remove_review_row(normalized, snapshot, 0)
    result = sync_review_corrections(pruned, new_snapshot)
    assert result.at[1, "value"] == "-0.375"
    assert result.at[1, "was_corrected"] == True
    assert result.at[1, "original_value"] == "-0.370"


def test_native_delete_first_row_preserves_original_audit(sample):
    snapshot, frame = sample
    before = deepcopy(snapshot)
    remaining, updated = reconcile_native_review_rows(
        frame.iloc[1:].reset_index(drop=True), snapshot
    )
    assert len(remaining) == len(updated["rows"]) == 2
    assert [r["measurement"] for r in updated["rows"]] == ["Peso", "Agua"]
    assert updated["excluded_review_rows"] == [{
        "measurement": "Ángulo", "original_value": "sin lectura"
    }]
    assert updated["raw_response"] == before["raw_response"]
    assert snapshot == before
    assert len(validate_review(remaining, updated)) == 2


def test_native_middle_delete_retains_edits_and_negative_decimals(sample):
    snapshot, frame = sample
    frame.at[0, "value"] = "8.20"
    frame.at[0, "correction_comment"] = "Confirmado en PDF"
    frame.at[2, "value"] = "-0.3700"
    frame.at[2, "correction_comment"] = "Cuatro decimales en reporte"
    remaining, updated = reconcile_native_review_rows(
        frame.iloc[[0, 2]].reset_index(drop=True), snapshot
    )
    assert [r["measurement"] for r in updated["rows"]] == ["Ángulo", "Agua"]
    assert remaining.loc[0, "value"] == "8.20"
    assert remaining.loc[1, "value"] == "-0.3700"
    assert remaining["was_corrected"].tolist() == [True, True]
    verified = validate_review(remaining, updated)
    assert [r["original_value"] for r in verified] == ["sin lectura", "-0.370"]


def test_native_delete_multiple_rows_once_and_again(sample):
    snapshot, frame = sample
    kept, first = reconcile_native_review_rows(
        frame.iloc[[0, 2]].reset_index(drop=True), snapshot
    )
    kept, second = reconcile_native_review_rows(
        kept.iloc[[1]].reset_index(drop=True), first
    )
    assert len(second["rows"]) == 1
    assert second["rows"][0]["measurement"] == "Agua"
    assert len(second["excluded_review_rows"]) == 2
    assert second["raw_response"] == snapshot["raw_response"]


def test_native_delete_distinguishes_same_original_value_by_labels(sample):
    snapshot, frame = sample
    extra = deepcopy(snapshot["rows"][2])
    extra["measurement"] = "Agua izquierda"
    snapshot["rows"].append(extra)
    frame = compact_review_table(pd.DataFrame(snapshot["rows"], columns=COLUMNS))
    reduced = frame.iloc[[0, 2, 3]].reset_index(drop=True)
    table, result = reconcile_native_review_rows(reduced, snapshot)
    assert [r["measurement"] for r in result["rows"]] == [
        "Ángulo", "Agua", "Agua izquierda"
    ]
    assert result["excluded_review_rows"][-1]["measurement"] == "Peso"
    assert len(table) == 3


def test_native_delete_same_original_value_removes_correct_distinct_row(sample):
    snapshot, _ = sample
    left = deepcopy(snapshot["rows"][2])
    right = deepcopy(left)
    left["measurement"] = "Brazo derecho ECW"
    right["measurement"] = "Brazo izquierdo ECW"
    snapshot["rows"] = [left, right]
    grid = compact_review_table(pd.DataFrame(snapshot["rows"], columns=COLUMNS))
    one, updated = reconcile_native_review_rows(grid.iloc[1:].reset_index(drop=True), snapshot)
    assert updated["rows"][0]["measurement"] == "Brazo izquierdo ECW"
    assert updated["excluded_review_rows"][0]["measurement"] == "Brazo derecho ECW"
    assert one.loc[0, "original_value"] == "-0.370"


def test_native_delete_rejects_indistinguishable_source_rows(sample):
    snapshot, _ = sample
    original = deepcopy(snapshot["rows"][2])
    snapshot["rows"] = [deepcopy(original), deepcopy(original)]
    grid = compact_review_table(pd.DataFrame(snapshot["rows"], columns=COLUMNS))
    with pytest.raises(ValueError, match="indistinguibles"):
        reconcile_native_review_rows(grid.iloc[:1].reset_index(drop=True), snapshot)


def test_native_delete_rejects_added_or_all_removed_rows(sample):
    snapshot, frame = sample
    larger = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError, match="agregar filas"):
        reconcile_native_review_rows(larger, snapshot)
    with pytest.raises(ValueError, match="al menos una medición"):
        reconcile_native_review_rows(frame.iloc[:0], snapshot)


def test_native_delete_rejects_forged_original_and_reorder(sample):
    snapshot, frame = sample
    forged = frame.iloc[1:].reset_index(drop=True).copy()
    forged.at[0, "original_value"] = "999.0"
    with pytest.raises(ValueError, match="valores originales"):
        reconcile_native_review_rows(forged, snapshot)
    reordered = frame.iloc[[2, 0]].reset_index(drop=True)
    with pytest.raises(ValueError, match="valores originales"):
        reconcile_native_review_rows(reordered, snapshot)


def test_native_edit_without_deletion_keeps_snapshot_identity(sample):
    snapshot, frame = sample
    frame.at[1, "value"] = "77.20"
    updated, retained = reconcile_native_review_rows(frame, snapshot)
    assert retained is snapshot
    assert updated.at[1, "was_corrected"] == True
    assert snapshot["rows"][1]["value"] == "75.20"
