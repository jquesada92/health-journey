"""Regression checks for the sticky InBody progress flow.

All tests are synthetic: no Gradio runtime, credentials, AI or SQL needed.
"""
import ast
from html.parser import HTMLParser
from pathlib import Path

import pytest

from inbody_mvp.inbody_flow import (
    INBODY_FLOW_CSS,
    STEPS,
    render_inbody_flow,
)

APP = (Path(__file__).resolve().parents[1] / "app.py").read_text()
INBODY = APP.split('with gr.Tab("InBody Upload"):', 1)[1].split(
    'with gr.Tab("Training Hub"):', 1
)[0]


class _StepParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.steps = []

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.steps.append(dict(attrs))


@pytest.mark.parametrize("active", range(1, 6))
def test_exactly_one_active_step_and_preceding_steps_completed(active):
    markup = render_inbody_flow(active)
    parser = _StepParser()
    parser.feed(markup)
    assert len(parser.steps) == len(STEPS) == 5
    assert sum("current" in item["class"] for item in parser.steps) == 1
    assert sum("done" in item["class"] for item in parser.steps) == active - 1
    assert parser.steps[active - 1].get("aria-current") == "step"
    assert f"Paso {active} de 5" in markup
    assert '<ol class="hj-flow-track">' in markup
    assert all(label in markup for label in STEPS)


def test_save_success_shows_all_steps_completed_without_active_step():
    markup = render_inbody_flow(5, saved=True)
    parser = _StepParser()
    parser.feed(markup)
    assert len(parser.steps) == 5
    assert all("done" in item["class"] for item in parser.steps)
    assert all("aria-current" not in item for item in parser.steps)
    assert "Examen guardado" in markup


@pytest.mark.parametrize("invalid", [0, 6, -1, "3", False])
def test_invalid_stage_fails_closed(invalid):
    with pytest.raises(ValueError):
        render_inbody_flow(invalid)


def test_sticky_style_targets_gradio_root_and_has_mobile_grid():
    assert "#hj-inbody-flow {" in INBODY_FLOW_CSS
    assert "position: sticky !important;" in INBODY_FLOW_CSS
    assert "z-index: 35;" in INBODY_FLOW_CSS
    assert "grid-template-columns: repeat(5, minmax(0, 1fr))" in INBODY_FLOW_CSS
    assert "@media (max-width: 600px)" in INBODY_FLOW_CSS
    assert '<nav aria-label="Progreso del registro InBody"' in render_inbody_flow()
    assert 'elem_id="hj-inbody-flow"' in INBODY
    assert "css=INBODY_FLOW_CSS" in APP


def test_real_actions_drive_progress_and_edit_invalidates_prior_validation():
    assert "inbody_flow = gr.HTML(" in INBODY
    assert "fn=progress_after_extract" in INBODY
    assert "fn=progress_after_validation" in INBODY
    assert "fn=progress_after_save" in INBODY
    assert "gemini_table.edit(" in INBODY
    assert "fn=progress_after_table_edit" in INBODY
    assert "inbody_clear.click(" in INBODY

    tree = ast.parse(APP)
    functions = {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
    }
    upload = ast.unparse(functions["progress_after_extract"])
    assert "if snapshot is not None" in upload
    assert "render_inbody_flow(3)" in upload
    assert "render_inbody_flow(2 if upload else 1)" in upload
    review = ast.unparse(functions["progress_after_validation"])
    assert "Revisión completa:" in review
    assert "render_inbody_flow(5)" in review
    assert "render_inbody_flow(4)" in review
    edit = ast.unparse(functions["progress_after_table_edit"])
    assert "render_inbody_flow(3)" in edit
    assert "Revisión pendiente:" in edit
    save = ast.unparse(functions["progress_after_save"])
    assert "saved=True" in save
    assert "gr.update()" in save


def test_flow_updates_do_not_reset_privacy_permissions_or_upload_snapshot():
    flow = INBODY.split("inbody_flow = gr.HTML(", 1)[1]
    clear = flow.split("inbody_clear.click(", 1)[1].split(
        'with gr.Tab("Training Hub"):', 1
    )[0] if 'with gr.Tab("Training Hub"):' in flow else flow.split("inbody_clear.click(", 1)[1]
    assert "session_ai_consent" not in clear
    assert "session_db_consent" not in clear
    assert "outputs=[inbody_flow]" in clear
    assert "gemini_save_status" in INBODY
