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
                    and k.value.id == "save_review_and_clear" for k in n.keywords)]
    assert len(save) == 1
    inputs = next(k.value for k in save[0].keywords if k.arg == "inputs")
    assert [x.id for x in inputs.elts] == [
        "gemini_table", "gemini_snapshot", "gemini_consent", "gemini_overwrite"
    ]

def test_clear_resets_consent_and_extraction():
    clears = [n for n in ast.walk(TREE) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == "ClearButton"]
    assert any({"gemini_consent", "gemini_snapshot", "gemini_table"} <=
               {x.id for x in n.args[0].elts if isinstance(x, ast.Name)}
               for n in clears)


def test_zerogpu_runtime_has_registered_optional_gpu_diagnostic():
    """ZeroGPU startup scans the actual Gradio event handler."""
    functions = [n for n in TREE.body if isinstance(n, ast.FunctionDef)
                 and n.name == "diagnose_zerogpu"]
    assert len(functions) == 1
    assert any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
               and isinstance(d.func.value, ast.Name)
               and d.func.value.id == "spaces" and d.func.attr == "GPU"
               for d in functions[0].decorator_list)
    handlers = [n for n in ast.walk(TREE) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == "click"]
    assert any(any(k.arg == "fn" and isinstance(k.value, ast.Name)
                   and k.value.id == "diagnose_zerogpu" for k in n.keywords)
               for n in handlers)
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text()
    assert "fn=extract_with_popup" in app
    assert "extract_gemini(state, consent, selected_model=model)" in app
    assert "popup_error(exc" in app
    assert "return keep_components(3)" in app
    assert "gr.Warning(message)" in app
    assert "raise gr.Error(" not in app
    assert "fn=review_with_popup" in app
    assert "fn=save_review_and_clear" in app
    assert not any(isinstance(n, ast.FunctionDef) and n.name == "extract_gemini"
                   for n in TREE.body)


def test_account_and_zerogpu_tools_are_not_visible_in_ui():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text()
    assert 'Seguridad de la cuenta (cambiar contraseña)' not in source
    assert 'Diagnóstico ZeroGPU (opcional)' not in source
    assert 'fn=change_login' not in source
    assert 'with gr.Column(visible=False):' in source
    assert '_zerogpu_keepalive = gr.Button(visible=False)' in source
    assert 'fn=diagnose_zerogpu, outputs=[], api_name=False' in source
    assert 'auth=authenticate_master_demo if password_login_enabled() else None' in source
