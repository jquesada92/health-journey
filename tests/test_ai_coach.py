"""Synthetic, privacy-preserving AI Coach contracts; no external API or database."""
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from inbody_mvp import ai_coach


def d(days_ago):
    return (date.today() - timedelta(days=days_ago)).isoformat()


def test_inbody_preserves_exact_decimals_separates_models_and_units():
    source = [
        {"exam_date": d(30), "section": "Muscle-Fat Analysis",
         "measurement": "Skeletal Muscle Mass", "value": "30.20",
         "unit": "kg", "modelo_inbody": "InBody 580"},
        {"exam_date": d(3), "section": "Muscle-Fat Analysis",
         "measurement": "Skeletal Muscle Mass", "value": "31.30",
         "unit": "kg", "modelo_inbody": "InBody 580"},
        {"exam_date": d(2), "section": "Muscle-Fat Analysis",
         "measurement": "Skeletal Muscle Mass", "value": "69.01",
         "unit": "lb", "modelo_inbody": "InBody 580"},
        {"exam_date": d(1), "section": "Muscle-Fat Analysis",
         "measurement": "Skeletal Muscle Mass", "value": "33.00",
         "unit": "kg", "modelo_inbody": "InBody 770"},
    ]
    output = ai_coach.summarize_inbody(source)
    assert output["distinct_series"] == 3
    filtered = [
        s for s in output["series"]
        if s["inbody_model"] == "InBody 580" and s["unit"] == "kg"
    ][0]
    assert filtered["latest_value"] == "31.30"
    assert filtered["previous_value"] == "30.20"
    assert filtered["absolute_change"] == "1.10"
    assert output["series"][0]["measurement"] == "Skeletal Muscle Mass"
    assert "person_id" not in str(output)
    assert "filename" not in str(output)


def test_inbody_rejects_unknown_and_non_finite_values_without_faking_change():
    output = ai_coach.summarize_inbody([
        {"exam_date": d(8), "section": "Obesity Analysis",
         "measurement": "PBF", "value": "NaN", "unit": "%"},
        {"exam_date": d(6), "section": "Obesity Analysis",
         "measurement": "PBF", "value": "-1.25", "unit": "%"},
    ])
    assert output["measurements_seen"] == 1
    assert output["series"][0]["latest_value"] == "-1.25"
    assert output["series"][0]["absolute_change"] is None


def test_training_summarizes_with_unit_separation_and_no_comments():
    rows = [
        {"exercise_key": "squat", "exercise": "Squat", "weight_unit": "kgs",
         "workout_date": d(25), "sets_count": 3,
         "reps_total": Decimal("20"), "max_weight": Decimal("60.00"),
         "volume": Decimal("1200.00")},
        {"exercise_key": "squat", "exercise": "Squat", "weight_unit": "kgs",
         "workout_date": d(5), "sets_count": 4,
         "reps_total": Decimal("24"), "max_weight": Decimal("65.00"),
         "volume": Decimal("1560.00")},
        {"exercise_key": "squat", "exercise": "Squat", "weight_unit": "lbs",
         "workout_date": d(2), "sets_count": 2,
         "reps_total": Decimal("20"), "max_weight": Decimal("145"),
         "volume": Decimal("2900")},
    ]
    summary = ai_coach.summarize_training(rows)
    assert summary["sets_recorded"] == 9
    assert summary["days_recorded"] == 3
    assert summary["distinct_exercises"] == 2
    metric = next(r for r in summary["exercises"] if r["weight_unit"] == "kgs")
    assert metric["max_weight_change"] == "5.00"
    assert metric["latest_positive_load_volume"] == "1560.00"
    assert "comment" not in str(summary)


def test_chat_requires_separate_consent_before_loading_private_data(monkeypatch):
    monkeypatch.setattr("inbody_mvp.prelogin_consent.has_consent", lambda *a, **k: False)
    with pytest.raises(PermissionError, match="Autoriza"):
        ai_coach.answer_coach_question(
            "¿Qué cambió?", [], "fake-report-id", "fuerza", "", 90,
            "gemini-3.8-flash", True, request=SimpleNamespace(),
        )


def test_server_rejects_client_checked_without_signed_consent(monkeypatch):
    monkeypatch.setattr("inbody_mvp.prelogin_consent.has_consent", lambda *a, **k: False)
    with pytest.raises(PermissionError):
        ai_coach.answer_coach_question(
            "¿Cómo mejorar?", [], "", "fuerza", "", 30,
            "gemini-3.8-flash", True,
        )


def test_no_private_raw_documents_ids_sent_in_chat_context():
    module = (Path(__file__).resolve().parents[1] / "inbody_mvp/ai_coach.py").read_text()
    assert "has_consent(request, \"coach\")" in module
    assert '"question": question' in module
    assert "raw_response" not in module
    assert "filename" not in module
    assert "source_sha256" not in module
    assert "SELECT" in module
    assert "DELETE FROM" not in module
    assert "UPDATE public." not in module
    assert "INSERT INTO" not in module


def test_project_is_initial_and_coach_has_controls():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text()
    assert 'visible=True, elem_id="hj-panel-project"' in app
    assert "gr.Markdown(PROJECT_OVERVIEW)" in app
    assert 'session_coach_consent = gr.Checkbox(' in app
    assert "fn=ask_coach" in app
    assert "fn=coach_choice" in app
    assert "coach_goals = gr.Textbox(" in app
    assert "coach_restrictions = gr.Textbox(" in app
    # Gradio 6 uses the messages format by default; the old type keyword crashes startup.
    assert 'coach_chat = gr.Chatbot(' in app
    assert 'label="Asistente fitness", height=430,' in app
    assert 'type="messages"' not in app
    assert 'with gr.Tab(' not in app


def test_gradio6_chatbot_instantiation_and_message_history():
    """Smoke test with the Gradio runtime, not just an app.py source assertion."""
    import gradio as gr

    chatbot = gr.Chatbot(
        label="Asistente fitness",
        height=430,
        value=[
            {"role": "user", "content": "¿Cómo voy?"},
            {"role": "assistant", "content": "Necesito mediciones comparables."},
        ],
    )
    assert chatbot.height == 430
    assert len(chatbot.value) == 2
    assert [message["role"] for message in chatbot.value] == ["user", "assistant"]
