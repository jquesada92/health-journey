"""Regression checks for consent decisions shared across Gradio tabs.

Use static AST checks so tests run without API credentials, databases or Gradio.
"""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app.py"
SOURCE = APP.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _call_for(variable):
    for node in ast.walk(TREE):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable
            for target in node.targets
        ):
            return node.value
    raise AssertionError(f"Component {variable} not declared")


def _click(event_owner):
    for node in ast.walk(TREE):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "click"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == event_owner
        ):
            return node
    raise AssertionError(f"Missing {event_owner}.click")


def _keyword_names(call, keyword):
    arg = next(k.value for k in call.keywords if k.arg == keyword)
    assert isinstance(arg, ast.List)
    return [item.id for item in arg.elts if isinstance(item, ast.Name)]


def test_three_prelogin_choices_restored_without_reasking_inside_app():
    from inbody_mvp.prelogin_consent import render_privacy_page

    page = render_privacy_page()
    for name, scope in (
        ("session_ai_consent", "ai_consent"),
        ("session_db_consent", "db_consent"),
        ("session_coach_consent", "coach_consent"),
    ):
        component = _call_for(name)
        assert isinstance(component, ast.Call)
        assert isinstance(component.func, ast.Attribute)
        assert component.func.attr == "State"
        assert any(
            keyword.arg == "value"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is False
            for keyword in component.keywords
        )
        assert f'name="{scope}"' in page
        assert f"{name} = gr.Checkbox(" not in SOURCE
    assert 'with gr.Accordion("Permisos de esta sesión"' not in SOURCE
    assert "return ai, db, coach_choice(request)" in SOURCE
    assert "fn=restore_session_consents" in SOURCE
    assert "outputs=[session_ai_consent, session_db_consent, session_coach_consent]" in SOURCE
    assert "set_consent(request," not in SOURCE




def test_ai_and_database_consent_wired_to_expected_actions():
    ai_inputs = _keyword_names(_click("gemini_extract"), "inputs")
    inbody_inputs = _keyword_names(_click("gemini_save"), "inputs")
    training_inputs = _keyword_names(_click("training_save"), "inputs")
    assert "session_ai_consent" in ai_inputs
    assert "session_db_consent" not in ai_inputs
    assert "session_db_consent" in inbody_inputs
    assert "session_db_consent" in training_inputs
    assert "session_ai_consent" not in inbody_inputs + training_inputs


def test_exam_save_and_upload_never_change_prelogin_consents():
    # The only UI event allowed to initialize these values is demo.load
    # from the signed server-side pre-login session. User actions do not
    # change or revoke them inside the application.
    for node in ast.walk(TREE):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "outputs" or not isinstance(kw.value, ast.List):
                continue
            names = {
                elt.id for elt in kw.value.elts if isinstance(elt, ast.Name)
            }
            if names & {
                "session_ai_consent", "session_db_consent",
                "session_coach_consent",
            }:
                assert (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "load"
                    and any(
                        k.arg == "fn"
                        and isinstance(k.value, ast.Name)
                        and k.value.id == "restore_session_consents"
                        for k in node.keywords
                    )
                ), "Only pre-login session initialization sets consent states"
    assert "gemini_consent_remote" not in SOURCE
    assert "training_consent" not in SOURCE




def test_backend_still_checks_opt_in_before_network_side_effects():
    module_dir = APP.parent / "inbody_mvp"
    for filename, function_name in (
        ("gemini_review.py", "extract_gemini"),
        ("gemini_review.py", "save_audit"),
        ("training_hub.py", "save_training_import"),
    ):
        source = (module_dir / filename).read_text(encoding="utf-8")
        parsed = ast.parse(source)
        function = next(
            node for node in parsed.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        checks = [
            node for node in ast.walk(function)
            if isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id == "consent"
            and any(isinstance(op, ast.IsNot) for op in node.ops)
        ]
        assert checks, f"{function_name} must reject missing consent"
