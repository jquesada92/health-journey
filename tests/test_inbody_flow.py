"""Regression checks for the viewport-fixed InBody progress navbar.

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
INBODY = APP.split('with gr.Column(visible=False, elem_id="hj-panel-inbody") as inbody_panel:', 1)[1].split(
    'with gr.Column(visible=False, elem_id="hj-panel-training") as training_panel:', 1
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


def test_fixed_navbar_is_viewport_attached_and_hides_outside_inbody():
    assert "#hj-inbody-fixedbar {" in INBODY_FLOW_CSS
    assert "position: fixed !important;" in INBODY_FLOW_CSS
    assert "top: 0 !important;" in INBODY_FLOW_CSS
    assert "z-index: 200;" in INBODY_FLOW_CSS
    assert "padding-top: 180px !important;" in INBODY_FLOW_CSS
    assert "padding-top: 146px !important;" in INBODY_FLOW_CSS
    assert "anchor-name: --hj-main-content;" in INBODY_FLOW_CSS
    assert "grid-template-columns: repeat(5, minmax(0, 1fr))" in INBODY_FLOW_CSS
    assert "@media (max-width: 600px)" in INBODY_FLOW_CSS
    assert '<nav aria-label="Progreso del registro InBody"' in render_inbody_flow()
    assert 'with gr.Column(visible=False, elem_id="hj-inbody-fixedbar") as inbody_navbar:' in APP
    assert 'elem_id="hj-inbody-flow"' in APP
    assert 'elem_id="hj-inbody-fixedbar"' not in INBODY
    assert "gr.update(visible=(section == \"inbody\"))" in APP
    assert "outputs=[inbody_navbar, *module_panels, *nav_buttons]" in APP
    assert "css=INBODY_FLOW_CSS + SIDEBAR_CSS + COACH_CHAT_CSS" in APP
    assert 'gr.Markdown("## InBody · Registrar un examen"' in INBODY
    assert '# Health Journey · Asistente virtual de fitness y bienestar' not in APP
    assert APP.index('with gr.Accordion("Permisos de esta sesión"') < APP.index('with gr.Column(elem_id="hj-module-content")')
    assert APP.index('with gr.Sidebar(') < APP.index('with gr.Accordion("Permisos de esta sesión"')
    assert "position: sticky !important;" not in INBODY_FLOW_CSS
    assert "display: flex;" not in INBODY_FLOW_CSS.split("#hj-inbody-fixedbar {", 1)[1].split("}", 1)[0]


def test_real_actions_drive_progress_and_edit_invalidates_prior_validation():
    assert "inbody_flow = gr.HTML(" in APP
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
    flow = INBODY
    clear = flow.split("inbody_clear.click(", 1)[1].split(
        'with gr.Column(visible=False, elem_id="hj-panel-training") as training_panel:', 1
    )[0] if 'with gr.Column(visible=False, elem_id="hj-panel-training") as training_panel:' in flow else flow.split("inbody_clear.click(", 1)[1]
    assert "session_ai_consent" not in clear
    assert "session_db_consent" not in clear
    assert "outputs=[inbody_flow]" in clear
    assert "gemini_save_status" in INBODY
