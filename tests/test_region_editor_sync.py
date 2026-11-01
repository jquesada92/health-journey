"""Regression: visual editor and table stay synchronized without event loops."""
import ast
import json
from pathlib import Path

import pandas as pd


def callbacks():
    source = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    chosen = [n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name in {"table_from_visual_editor", "visual_editor_from_table"}]
    ns = {"gr": type("Gradio", (), {"Error": ValueError})}
    exec(compile(ast.Module(body=chosen, type_ignores=[]), "app.py", "exec"), ns)
    return ns


def test_add_remove_regions_reflect_in_table():
    fn = callbacks()["table_from_visual_editor"]
    payload = {"pages": [{"number": 1}], "rows": [[1, "header", 0, 0, 100, 80, True, None]]}
    rows, approved = fn(json.dumps(payload))
    assert len(rows) == 1 and approved is None
    payload["rows"].append([1, "impedance", 10, 90, 110, 150, True, None])
    rows, _ = fn(json.dumps(payload))
    assert len(rows) == 2
    payload["rows"].pop(0)
    rows, _ = fn(json.dumps(payload))
    assert len(rows) == 1 and rows[0][1] == "impedance"


def test_table_edits_update_canvas_without_losing_image():
    fn = callbacks()["visual_editor_from_table"]
    state = {"pages": [{"number": 1, "url": "data:image/jpeg;base64,abc"}],
             "metadata": {"hash": "opaque"}, "rows": []}
    frame = pd.DataFrame([[1, "header", 0, 0, 120, 75, True, None]])
    updated, approval = fn(frame, json.dumps(state))
    parsed = json.loads(updated)
    assert parsed["rows"][0][:6] == [1, "header", 0, 0, 120, 75]
    assert parsed["pages"] == state["pages"]
    assert approval is None


def test_input_events_are_connected_without_change_feedback_loop():
    code = Path("app.py").read_text(encoding="utf-8")
    assert "visual_editor.input(" in code
    assert "regions_table.input(" in code
    assert "fn=table_from_visual_editor" in code
    assert "fn=visual_editor_from_table" in code
