"""Synthetic contract tests for explicit external-provider consent."""
import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def test_gemini_consent_checked_before_provider_key_or_api_call():
    source = (ROOT / "inbody_mvp/gemini_review.py").read_text()
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "extract_gemini")
    lines = fn.body
    assert "if not upload_state" in ast.unparse(lines[0])
    assert "if consent is not True" in ast.unparse(lines[1])
    callback_source = ast.get_source_segment(source, fn)
    assert callback_source.index("if consent is not True:") < callback_source.index("api_key =")

    # Test guard independently of heavy Gradio runtime in CI.
    fn.decorator_list = []
    fn.returns = None
    for arg in fn.args.args:
        arg.annotation = None
    class UiError(Exception):
        pass
    scope = {"_ui_error": UiError}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 "<gemini guard>", "exec"), scope)
    try:
        scope["extract_gemini"]({"filename": "synthetic.jpg", "data": b"x"}, False)
    except UiError as exc:
        assert "autorizar" in str(exc)
    else:
        raise AssertionError("Consentimiento obligatorio")


def test_ui_supplies_explicit_remote_consent_and_resets_on_upload():
    tree = ast.parse((ROOT / "app.py").read_text())
    checkbox = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "gemini_consent_remote"
                        for t in n.targets)]
    assert len(checkbox) == 1
    assert next(k.value.value for k in checkbox[0].value.keywords
                if k.arg == "value") is False
    text = (ROOT / "app.py").read_text()
    assert "inputs=[gemini_upload_state, gemini_consent_remote, gemini_model_selector]" in text
    assert "outputs=[gemini_snapshot, gemini_consent_remote]" in text
