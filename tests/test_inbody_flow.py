"""Regression checks for the viewport-fixed InBody progress navbar.

All tests are synthetic: no Gradio runtime, credentials, AI or SQL needed.
"""
import ast
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import pytest

from inbody_mvp.inbody_flow import (
    INBODY_FLOW_CSS,
    INBODY_NEXT_STEP_JS,
    STEPS,
    render_inbody_flow,
    review_step_ready,
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
    assert "inbody_clear.click(" not in INBODY
    assert "gemini_review_continue.click(" in INBODY
    assert "finish_review_step" in INBODY
    assert "INBODY_NEXT_STEP_JS" in APP

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
    assert "render_inbody_flow(1)" in save
    assert "hj-inbody-step-1" in save
    assert "gr.update()" in save


def test_reset_after_save_clears_fields_without_revoking_consents():
    assert "gr.ClearButton(" not in INBODY
    assert "Limpiar examen (conservar permisos)" not in APP
    assert "save_review_and_clear" in INBODY
    assert "gr.Info(visible_message)" in INBODY
    assert "return keep_components(16)" in INBODY

    save_output_section = INBODY.split("gemini_save.click(", 1)[1].split(
        "concurrency_limit=1,", 1
    )[0]
    for field in (
        "gemini_upload", "gemini_upload_state", "gemini_snapshot",
        "gemini_preview", "gemini_preview_status", "gemini_table",
        "gemini_status", "gemini_overwrite", "gemini_file_status",
        "gemini_review_status", "header_exam_datetime",
        "header_filename", "header_person_id", "header_age",
        "header_correction_reason",
    ):
        assert field in save_output_section

    after_save = INBODY.split("fn=progress_after_save", 1)[1]
    assert "gemini_save_status" in after_save
    assert "inbody_navigation_target" in after_save
    assert "INBODY_NEXT_STEP_JS" in after_save
    save = INBODY.split("def save_review_and_clear(", 1)[1].split(
        "def progress_after_save(", 1
    )[0]
    assert "session_ai_consent" not in save
    assert "session_coach_consent" not in save
    assert "session_db_consent" not in save
    assert "return keep_components(16)" in save
    assert "gr.Info(visible_message)" in save


def test_auto_advance_only_after_successful_stage_completion():
    tree = ast.parse(APP)
    funcs = {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
    }
    extract = ast.unparse(funcs["progress_after_extract"])
    assert 'hj-inbody-step-3' in extract
    assert "render_inbody_flow(2 if upload else 1)" in extract
    assert "hj-inbody-step-3" in extract

    review = ast.unparse(funcs["finish_review_step"])
    assert "review_step_ready(table, snapshot)" in review
    assert 'hj-inbody-step-4' in review
    assert "gr.update()" in review
    assert "return" in review

    validate = ast.unparse(funcs["progress_after_validation"])
    assert 'hj-inbody-step-5' in validate
    assert 'Revisión completa:' in validate
    assert "render_inbody_flow(4)" in validate

    save = ast.unparse(funcs["progress_after_save"])
    assert 'Guardado en la base de datos:' in save
    assert 'hj-inbody-step-1' in save
    assert "gr.update()" in save

    assert APP.count("js=INBODY_NEXT_STEP_JS") == 5
    for n in range(1, 6):
        assert f'elem_id="hj-inbody-step-{n}"' in INBODY
        assert f'"hj-inbody-step-{n}"' in INBODY_NEXT_STEP_JS
        assert f"#hj-inbody-step-{n}" in INBODY_FLOW_CSS

    assert "scrollIntoView" in INBODY_NEXT_STEP_JS
    assert "prefers-reduced-motion" in INBODY_NEXT_STEP_JS
    assert 'document.getElementById("hj-panel-inbody")' in INBODY_NEXT_STEP_JS


def test_review_navigation_requires_actual_reviewed_measurements():
    frame = pd.DataFrame({"reviewed": [True, False]})
    assert review_step_ready(frame, {"sha256": "synthetic"})[0] is False
    assert "1 mediciones pendientes" in review_step_ready(
        frame, {"sha256": "synthetic"}
    )[1]
    frame.loc[1, "reviewed"] = True
    assert review_step_ready(frame, {"sha256": "synthetic"}) == (True, "")
    assert review_step_ready(frame, None)[0] is False
    assert review_step_ready(pd.DataFrame(), {"sha256": "synthetic"})[0] is False
