"""Pre-extraction duplicate detection uses private filename existence only.

Synthetic tests. Never contact Neon or Gemini and never use real patient files.
"""
import hashlib

import pytest

from inbody_mvp import gemini_review as review


@pytest.fixture
def uploaded():
    return {"filename": "sample-01.jpg", "data": b"synthetic report bytes"}


@pytest.mark.parametrize("answer,expected", [
    ("Este nombre de archivo ya fue procesado en Neon. No es necesario extraerlo nuevamente.", "duplicate"),
    ("Archivo nuevo: no existe un registro con ese nombre.", "new"),
    ("La verificación anticipada no está disponible.", "unverified"),
    ("Se verificará si el archivo ya fue procesado al guardarlo.", "unverified"),
])
def test_preflight_decision_is_explicit_and_bound_to_bytes(monkeypatch, uploaded, answer, expected):
    observed = []
    def check(state, profile=None, request=None):
        observed.append(state)
        return answer
    monkeypatch.setattr(review, "check_processed_filename", check)
    status = review.preflight_processed_upload(uploaded)
    assert status["status"] == expected
    assert status["sha256"] == hashlib.sha256(uploaded["data"]).hexdigest()
    assert observed == [uploaded]
    assert "tokens" in status["message"] if expected != "new" else True


def test_no_file_does_not_query_neon(monkeypatch):
    monkeypatch.setattr(
        review, "check_processed_filename",
        lambda *args, **kwargs: pytest.fail("Unexpected DB lookup")
    )
    assert review.preflight_processed_upload(None)["status"] == "empty"
    assert review.preflight_processed_upload({"filename": "x.pdf"})["status"] == "empty"


def test_same_name_different_bytes_has_different_local_fingerprint(monkeypatch, uploaded):
    monkeypatch.setattr(
        review, "check_processed_filename",
        lambda *a, **k: "Archivo nuevo: no existe un registro con ese nombre."
    )
    a = review.preflight_processed_upload(uploaded)
    b = review.preflight_processed_upload(dict(uploaded, data=b"other bytes"))
    assert a["sha256"] != b["sha256"]


def test_status_does_not_include_report_bytes_or_personal_information(monkeypatch, uploaded):
    monkeypatch.setattr(
        review, "check_processed_filename",
        lambda *a, **k: "Este nombre de archivo ya fue procesado en Neon."
    )
    status = review.preflight_processed_upload(uploaded)
    assert uploaded["data"] not in repr(status).encode()
    assert "filename" not in status
    assert set(status) == {"status", "sha256", "message"}
