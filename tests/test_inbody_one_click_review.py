"""Guardar cambios approves the edited InBody grid once without row-by-row toggles.

No provider, database, or personal report is used by these regression tests.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from inbody_mvp.gemini_review import (
    COLUMNS, compact_review_table, reconcile_native_review_rows, review_status,
)

APP = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


def _review_callback():
    """Exercise the app's real callback body without starting Gradio."""
    tree = ast.parse(APP)
    fn = next(node for node in ast.walk(tree)
              if isinstance(node, ast.FunctionDef)
              and node.name == "review_with_popup")
    notices = []
    gr = SimpleNamespace(
        Warning=lambda message: notices.append(("warning", message)),
        Info=lambda message: notices.append(("info", message)),
        update=lambda: None,
    )
    scope = {
        "gr": gr,
        "reconcile_native_review_rows": reconcile_native_review_rows,
        "review_status": review_status,
        "exam_header_edits": lambda dt, filename, pid, age, comment: {
            "exam_datetime": dt, "filename": filename, "person_id": pid,
            "age": age, "correction_comment": comment,
        },
        "popup_error": lambda error, fallback: notices.append(
            ("error", str(error))
        ),
    }
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=[fn], type_ignores=[])), "<review_callback>", "exec"),
        scope)
    return scope["review_with_popup"], notices


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
    snapshot = {"rows": rows, "header": header, "filename": "synthetic.png"}
    table = compact_review_table(pd.DataFrame(rows, columns=COLUMNS))
    return snapshot, table


def _confirm(callback, table, snapshot):
    return callback(table, snapshot, "2025-01-26 14:20:00",
                    "synthetic.png", "00077", "33", "")


def test_guardar_cambios_approves_all_retained_rows_and_uses_edited_values():
    snapshot, table = _exam()
    callback, notices = _review_callback()
    table.at[0, "value"] = "75.30"
    table.at[0, "was_corrected"] = False
    table.at[0, "correction_comment"] = "Comparado con el original"
    table.at[1, "value"] = "-0.3700"
    table.at[1, "correction_comment"] = "Confirmado en el PDF"

    approved, new_snapshot, message = _confirm(callback, table, snapshot)

    assert message.startswith("Revisión completa:")
    assert approved["reviewed"].eq(True).all()
    assert approved["was_corrected"].eq(True).all()
    assert approved["value"].tolist() == ["75.30", "-0.3700"]
    assert approved["original_value"].tolist() == ["75.20", "-0.370"]
    assert snapshot["rows"][0]["value"] == "75.20"
    assert new_snapshot["rows"][0]["value"] == "75.20"
    assert [kind for kind, _ in notices] == ["info"]


def test_invalid_correction_keeps_table_but_does_not_approve_rows():
    snapshot, table = _exam()
    callback, notices = _review_callback()
    table.at[0, "value"] = "75.30"
    # Deliberately missing the correction comment.
    retained, new_snapshot, message = _confirm(callback, table, snapshot)
    assert message == ""
    assert not retained["reviewed"].any()
    assert retained.loc[0, "value"] == "75.30"
    assert new_snapshot["rows"][0]["value"] == "75.20"
    assert [kind for kind, _ in notices] == ["warning"]


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
    assert "if consent is not True or not has_consent" not in body
    assert "state, consent, selected_model=model" in body
