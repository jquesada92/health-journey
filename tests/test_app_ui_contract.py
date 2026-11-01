"""Static contract for the Gemini review and audit UI."""
import ast
from pathlib import Path

TREE = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())

def _widget(name):
    matches = [n for n in ast.walk(TREE) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    assert len(matches) == 1, name
    return matches[0].value

def test_private_consent_is_explicit_and_off_by_default():
    widget = _widget("gemini_consent")
    assert widget.func.attr == "Checkbox"
    assert next(k.value.value for k in widget.keywords if k.arg == "value") is False

def test_gemini_save_requires_consent_and_snapshot():
    save = [n for n in ast.walk(TREE) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == "click"
            and any(k.arg == "fn" and isinstance(k.value, ast.Name)
                    and k.value.id == "save_audit" for k in n.keywords)]
    assert len(save) == 1
    inputs = next(k.value for k in save[0].keywords if k.arg == "inputs")
    assert [x.id for x in inputs.elts] == [
        "gemini_table", "gemini_snapshot", "gemini_consent"
    ]

def test_clear_resets_consent_and_extraction():
    clears = [n for n in ast.walk(TREE) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == "ClearButton"]
    assert any({"gemini_consent", "gemini_snapshot", "gemini_table"} <=
               {x.id for x in n.args[0].elts if isinstance(x, ast.Name)}
               for n in clears)
