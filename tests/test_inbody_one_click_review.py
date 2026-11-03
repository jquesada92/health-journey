"""One Save operation validates reviewed InBody rows and persists corrections.

Synthetic-only callback tests: no database or Gemini network access.
"""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from inbody_mvp.gemini_review import (
    COLUMNS, DISPLAY_COLUMNS, compact_review_table,
    reconcile_native_review_rows, validate_review,
)

APP = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


def _save_callback(*, consent=True):
    source = ast.parse(APP)
    fn = next(node for node in ast.walk(source)
              if isinstance(node, ast.FunctionDef)
              and node.name == "save_review_and_clear")
    notices = []
    persisted = []

    def fake_save(table, snapshot, authorized, overwrite, header_edits):
        # The production save_audit validates BEFORE its SQL transaction.
        verified = validate_review(table, snapshot, header_edits)
        persisted.append((verified, snapshot, authorized, overwrite))
        return f"Guardado en Neon: {len(verified)} mediciones"

    scope = {
        "gr": SimpleNamespace(
            Warning=lambda message: notices.append(("warning", message)),
            Info=lambda message: notices.append(("info", message)),
            update=lambda **kwargs: None,
        ),
        "pd": pd,
        "GEMINI_DISPLAY_COLUMNS": DISPLAY_COLUMNS,
        "has_consent": lambda req, kind: consent and kind == "db",
        "exam_header_edits": lambda stamp, filename, person, age, reason: {
            "exam_datetime": stamp, "filename": filename,
            "person_id": person, "age": age,
            "correction_comment": reason,
        },
        "reconcile_native_review_rows": reconcile_native_review_rows,
        "save_audit": fake_save,
        "popup_error": lambda err, fallback: notices.append(
            ("error", str(err)),
        ),
        "keep_components": lambda count: tuple(["unchanged"] * count),
    }
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=[fn], type_ignores=[])), "<save_callback>", "exec"),
        scope)
    return scope["save_review_and_clear"], notices, persisted


def _exam():
    header = {
        "exam_datetime": "2025-01-26 14:20:00", "filename": "synthetic.png",
        "person_id": "00077", "age": 33,
    }
    rows = [
        dict(header, section="Composición", measurement="Peso",
             value="75.20", unit="kg", original_value="75.20",
             was_corrected=False, correction_comment="", reviewed=False),
        dict(header, section="Segmentos", measurement="Ángulo",
             value="-0.370", unit="°", original_value="-0.370",
             was_corrected=False, correction_comment="", reviewed=False),
    ]
    snapshot = {
        "rows": deepcopy(rows), "header": header, "filename": "synthetic.png"
    }
    return snapshot, compact_review_table(pd.DataFrame(rows, columns=COLUMNS))


def _save(callback, table, snapshot, *, approved=True):
    return callback(
        table, snapshot, approved, False, "2025-01-26 14:20:00",
        "synthetic.png", "00077", "33", "",
    )


def test_single_button_persists_corrected_values_and_preserves_originals():
    snapshot, table = _exam()
    callback, notices, persisted = _save_callback()
    table.loc[:, "reviewed"] = True
    table.loc[0, "value"] = "75.30"
    table.loc[0, "correction_comment"] = "Comparado con el original"
    table.loc[1, "value"] = "-0.3700"
    table.loc[1, "correction_comment"] = "Corregido con el PDF"

    result = _save(callback, table, snapshot)

    assert result[0].startswith("Guardado en la base de datos:")
    assert len(persisted) == 1
    rows, audit_snapshot, authorized, overwrite = persisted[0]
    assert [row["value"] for row in rows] == ["75.30", "-0.3700"]
    assert [row["original_value"] for row in rows] == ["75.20", "-0.370"]
    assert [row["was_corrected"] for row in rows] == [True, True]
    assert [source["value"] for source in snapshot["rows"]] == [
        "75.20", "-0.370"
    ]
    assert audit_snapshot is snapshot
    assert authorized is True
    assert overwrite is False
    assert [kind for kind, _ in notices] == ["info"]
    assert result[2] is None  # upload snapshot cleared only after DB success


def test_missing_review_or_correction_does_not_write_or_clear_table():
    snapshot, table = _exam()
    callback, notices, persisted = _save_callback()
    table.loc[0, "reviewed"] = True
    # Second row unreviewed; no persistence.
    result = _save(callback, table, snapshot)
    assert result == ("unchanged",) * 16
    assert not persisted
    assert [kind for kind, _ in notices] == ["error"]
    table.loc[1, "reviewed"] = True
    table.loc[0, "value"] = "75.30"  # missing correction_comment
    notices.clear()
    result = _save(callback, table, snapshot)
    assert result == ("unchanged",) * 16
    assert not persisted
    assert [kind for kind, _ in notices] == ["error"]


def test_native_row_deletion_is_reconciled_inside_single_save():
    snapshot, table = _exam()
    callback, notices, persisted = _save_callback()
    kept = table.iloc[[1]].reset_index(drop=True)
    kept.loc[:, "reviewed"] = True
    result = _save(callback, kept, snapshot)
    assert result[0].startswith("Guardado en la base de datos:")
    rows, updated_snapshot, _, _ = persisted[0]
    assert len(rows) == 1
    assert rows[0]["original_measurement"] == "Ángulo"
    assert updated_snapshot["excluded_review_rows"][0]["measurement"] == "Peso"


def test_unsigned_database_consent_blocks_save_before_reconciliation():
    snapshot, table = _exam()
    callback, notices, persisted = _save_callback(consent=False)
    result = _save(callback, table, snapshot)
    assert result == ("unchanged",) * 16
    assert not persisted
    assert [kind for kind, _ in notices] == ["error"]


def test_extraction_uses_authoritative_server_consent_not_stale_gradio_state():
    node = next(node for node in ast.walk(ast.parse(APP))
                if isinstance(node, ast.FunctionDef)
                and node.name == "extract_with_popup")
    body = ast.get_source_segment(APP, node)
    assert 'consent = has_consent(request, "ai")' in body
    assert body.index('consent = has_consent(request, "ai")') < body.index(
        "extract_gemini("
    )
    assert "if not consent:" in body
    assert "state, consent, selected_model=model" in body
