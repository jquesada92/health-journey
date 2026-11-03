"""Training Hub integration does not alter the InBody workflow."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
APP = (BASE / "app.py").read_text(encoding="utf-8")
SQL = (BASE / "migrations/008_fitnotes_training_hub.sql").read_text(encoding="utf-8")


def test_gradio_upload_preview_consent_save_and_read():
    assert 'with gr.Column(visible=False, elem_id="hj-panel-training") as training_panel:' in APP
    assert 'file_types=[".csv"]' in APP
    assert "fn=parse_training_with_popup" in APP
    assert "fn=save_training_with_popup" in APP
    assert "fn=recent_training_with_popup" in APP
    assert "require_database_access(profile, request=request)" in APP
    assert "inputs=[training_state, session_db_consent, training_overwrite]" in APP
    assert 'label="Vista previa del CSV (solo lectura)"' in APP
    assert 'session_db_consent = gr.Checkbox(' in APP
    assert 'training_consent = gr.Checkbox(' not in APP


def test_private_training_permissions_and_stable_key():
    assert "UNIQUE (owner_key, workout_date, exercise_key, set_number)" in SQL
    assert "UNIQUE (owner_key, source_sha256)" in SQL
    assert "REVOKE ALL ON public.hj_training_sets FROM PUBLIC;" in SQL
    assert "FROM health_journey_public, health_journey_demo_writer" in SQL
    assert "TO health_journey_app, health_journey_runtime" in SQL
