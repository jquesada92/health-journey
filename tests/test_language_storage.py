"""Synthetic data only; these tests never connect to Neon."""
from __future__ import annotations

import pandas as pd
import pytest
from types import SimpleNamespace

from inbody_mvp.extractor import parse_text
from inbody_mvp.language import detect_report_language
from inbody_mvp.review import review_table
from inbody_mvp.storage import database_enabled, require_database_access, require_report_access, prepare_confirmed_exam


def test_spanish_inbody_headings():
    text = "Análisis de la Composición Corporal\nAnálisis Músculo-Grasa\nPorcentaje de Grasa Corporal"
    assert detect_report_language(text) == "ES"


def test_english_inbody_headings():
    text = "Body Composition Analysis\nMuscle-Fat Analysis\nPercent Body Fat"
    assert detect_report_language(text) == "EN"


@pytest.mark.parametrize("text", [
    "Weight 71.2 kg",
    "InBody 580",
    "Body Composition Analysis\nAnálisis de la Composición Corporal",
    "",
])
def test_inconclusive_does_not_guess(text):
    assert detect_report_language(text) == "UNKNOWN"


def _fixture():
    result = parse_text([(
        "ID: ANON-01\nInBody 580\nBody Composition Analysis\n"
        "Muscle-Fat Analysis\nWeight 70.4 kg\nPhase Angle Left Leg (50 kHz) 6.1 °",
        "pdf_text"
    )], filename="synthetic.pdf", digest="a" * 64)
    return result, review_table(result)


def test_language_saved_as_exam_metadata():
    result, table = _fixture()
    assert result.idioma_reporte == "EN"
    payload = prepare_confirmed_exam(
        result.model_dump(mode="json"), table, "ANON-01", "InBody 580",
        "2026-10-31T10:30:00", 34, "EN",
    )
    assert payload.idioma_reporte == "EN"
    assert payload.source_sha256 == "a" * 64
    assert len(payload.measurements) == 2
    assert payload.measurements[1].segmento == "left_leg"
    assert payload.measurements[1].frecuencia_khz == 50.0


def test_missing_timestamp_rejected():
    result, table = _fixture()
    with pytest.raises(ValueError, match="fecha y hora"):
        prepare_confirmed_exam(result.model_dump(mode="json"), table, "ANON-01",
                               "InBody 580", "", 34, "EN")


def test_missing_numeric_value_rejected():
    result, table = _fixture()
    table.loc[0, "valor_medida"] = float("nan")
    with pytest.raises(ValueError, match="valor ambiguo"):
        prepare_confirmed_exam(result.model_dump(mode="json"), table, "ANON-01",
                               "InBody 580", "2026-10-31T10:30:00", 34, "EN")


def test_public_space_never_allows_writes(monkeypatch):
    monkeypatch.setenv("ENABLE_PERSISTENCE", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake:fake@localhost/db?sslmode=require")
    monkeypatch.setenv("SPACE_ID", "test/private")
    assert database_enabled() is False
    monkeypatch.delenv("SPACE_ID")
    assert database_enabled() is True
    monkeypatch.setenv("ENABLE_PERSISTENCE", "0")
    assert database_enabled() is False

def test_space_oauth_allowlist_enforced_per_request(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "jaqo/health-journey")
    monkeypatch.setenv("ENABLE_PERSISTENCE", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@invalid/db?sslmode=require")
    monkeypatch.setenv("HF_ALLOWED_USERS", "jaqo")
    assert database_enabled() is True
    for profile in (None, SimpleNamespace(username="other"), SimpleNamespace(username="")):
        with pytest.raises(PermissionError):
            require_database_access(profile)
    require_database_access(SimpleNamespace(name="Nombre Visible", username="JAQO"))
    monkeypatch.delenv("HF_ALLOWED_USERS")
    assert database_enabled() is False
    with pytest.raises(PermissionError):
        require_database_access(SimpleNamespace(username="jaqo"))


def test_local_owner_only_when_explicitly_enabled(monkeypatch):
    monkeypatch.delenv("SPACE_ID", raising=False)
    monkeypatch.setenv("ENABLE_PERSISTENCE", "0")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@invalid/db?sslmode=require")
    assert database_enabled() is False
    with pytest.raises(PermissionError):
        require_database_access(None)
    monkeypatch.setenv("ENABLE_PERSISTENCE", "1")
    require_database_access(None)


def test_display_name_is_not_an_authentication_identifier(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "jaqo/health-journey")
    monkeypatch.setenv("ENABLE_PERSISTENCE", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake:fake@invalid/db?sslmode=require")
    monkeypatch.setenv("HF_ALLOWED_USERS", "jaqo")
    # A user can have a display name that coincidentally matches the owner.
    with pytest.raises(PermissionError):
        require_database_access(SimpleNamespace(name="jaqo", username="different-user"))
    # A valid username must pass regardless of the display name.
    require_database_access(SimpleNamespace(name="Alias visible", username="jaqo"))


def test_upload_and_csv_authorization_independent_from_neon(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "jaqo/health-journey")
    monkeypatch.setenv("ENABLE_PERSISTENCE", "0")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("HF_ALLOWED_USERS", "jaqo")
    assert database_enabled() is False
    require_report_access(SimpleNamespace(name="Otra persona", username="jaqo"))
    with pytest.raises(PermissionError):
        require_report_access(SimpleNamespace(name="jaqo", username="otro"))
    with pytest.raises(PermissionError):
        require_report_access(None)
    monkeypatch.delenv("HF_ALLOWED_USERS")
    require_report_access(None)  # QA without Neon/allowlist: synthetic files only
