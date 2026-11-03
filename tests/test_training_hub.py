"""Synthetic FitNotes tests; never commit private workout exports."""
import csv
import hashlib
import io

import pytest

from inbody_mvp.training_hub import (
    COLUMNS, MAX_CSV_BYTES, _duration, parse_fitnotes_bytes,
    preview_training, _owner_key,
)


def csv_bytes(*rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def sample():
    return csv_bytes(
        ["2026-10-01", "Squat", "Legs", "8.20", "kgs", "10", "", "", "", ""],
        ["2026-10-01", "Squat", "Legs", "8.20", "kgs", "10", "", "", "", ""],
        ["2026-10-01", "Suitcase Carry", "Abs", "-3.50", "kgs", "", "", "", "0:01:20", "Dropset *"],
        ["2026-10-02", "Squat", "Legs", "0.00", "kgs", "8", "", "", "", ""],
    )


def test_same_day_identical_sets_retained_in_sequence():
    content = sample()
    result = parse_fitnotes_bytes(content, "FitNotes_Export.csv")
    assert len(result["rows"]) == 4
    assert [r["set_number"] for r in result["rows"]] == [1, 2, 1, 1]
    assert [r["source_row_number"] for r in result["rows"]] == [2, 3, 4, 5]
    assert result["days"] == 2
    assert result["exercises"] == 2
    assert result["source_sha256"] == hashlib.sha256(content).hexdigest()


def test_numeric_scale_negative_values_missing_reps_and_duration():
    rows = parse_fitnotes_bytes(sample())["rows"]
    assert rows[0]["weight"] == "8.20"
    assert rows[2]["weight"] == "-3.50"
    assert rows[3]["weight"] == "0.00"
    assert rows[2]["reps"] is None
    assert rows[2]["duration_seconds"] == 80
    assert rows[2]["comment"] == "Dropset *"
    preview = preview_training({"rows": rows})
    assert preview.iloc[0]["Peso"] == "8.20"
    assert preview.iloc[2]["Peso"] == "-3.50"


def test_bom_utf8_and_unrecognized_exercise_allowed():
    content = b"\xef\xbb\xbf" + csv_bytes(
        ["2026-10-01", "New exercise", "Custom", "20.01", "lbs", "2", "", "", "", ""]
    )
    result = parse_fitnotes_bytes(content)
    assert result["rows"][0]["exercise"] == "New exercise"


@pytest.mark.parametrize("value", ["2026-99-01", "invalid", ""])
def test_invalid_dates_rejected(value):
    with pytest.raises(ValueError, match="fecha"):
        parse_fitnotes_bytes(csv_bytes(
            [value, "Squat", "Legs", "20", "kgs", "8", "", "", "", ""]
        ))


def test_incompatible_header_rejected():
    with pytest.raises(ValueError, match="Encabezado"):
        parse_fitnotes_bytes(b"Date,Exercise,Weight\n2026-10-01,Squat,20\n")


@pytest.mark.parametrize("value", ["NaN", "inf", "1e9999", "not a number"])
def test_nonfinite_or_invalid_numeric_rejected(value):
    with pytest.raises(ValueError):
        parse_fitnotes_bytes(csv_bytes(
            ["2026-10-01", "Squat", "Legs", value, "kgs", "8", "", "", "", ""]
        ))


def test_invalid_times_and_large_files_rejected():
    for value in ("0:61:00", "-1:00:00", "bad"):
        with pytest.raises(ValueError):
            _duration(value, 2)
    with pytest.raises(ValueError, match="10 MB"):
        parse_fitnotes_bytes(b"X" * (MAX_CSV_BYTES + 1))


def test_requires_authorized_owner_not_unauthenticated_master(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "jaqo/health-journey")
    monkeypatch.setattr("inbody_mvp.training_hub.require_database_access", lambda *a, **k: None)
    monkeypatch.setattr("inbody_mvp.training_hub.master_demo_authenticated", lambda request: False)
    monkeypatch.setattr("inbody_mvp.training_hub.password_login_enabled", lambda: False)
    with pytest.raises(PermissionError, match="iniciar sesión"):
        _owner_key()
    profile = type("Profile", (), {"username": "JAQO"})()
    assert _owner_key(profile) == "hf:jaqo"
