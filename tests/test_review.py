import csv
import io
import pytest

from inbody_mvp.extractor import parse_text
from inbody_mvp.review import REVIEW_COLUMNS, export_draft_csv, review_table


def rows(text):
    return review_table(parse_text([(text, "pdf_text")]))


def test_columns_and_unknown_are_preserved():
    table = rows("Novel Metric 8.2 %\nPhase Angle Left Leg (50 kHz) 5.8 °")
    assert list(table.columns) == REVIEW_COLUMNS
    assert len(table) == 2
    assert "sin_clasificar" in table.variable_medida.values


def test_csv_preserves_segment_frequency_and_missing_metadata():
    table = rows("Phase Angle Left Leg (50 kHz) 5.8 °\nWeight 74.1 kg")
    content = export_draft_csv(table, "ANON-01", "InBody 770", None, None)
    exported = list(csv.DictReader(io.StringIO(content)))
    assert exported[0]["variable_medida"] == "phase_angle__left_leg__50khz"
    assert exported[0]["valor_medida"] == "5.8"
    assert exported[0]["edad"] == ""
    assert exported[1]["variable_medida"] == "weight"


def test_invalid_values_rejected():
    table = rows("Weight 74.1 kg")
    table["valor_medida"] = table["valor_medida"].astype(object)
    table.loc[0, "valor_medida"] = "not-a-number"
    with pytest.raises(ValueError):
        export_draft_csv(table, "ANON-01", "InBody 770", None, 34)
    table.loc[0, "valor_medida"] = 74.1
    with pytest.raises(ValueError):
        export_draft_csv(table, "ANON-01", "InBody 770", "not-a-date", 34)
    with pytest.raises(ValueError):
        export_draft_csv(table, "ANON-01", "InBody 770", "2026-10-28T09:35", 34.5)


def test_no_measurements_cannot_export():
    with pytest.raises(ValueError):
        export_draft_csv(rows("Fecha: 28/10/2026"), None, None, None, None)


def test_csv_formula_escape():
    table = rows("Weight 74.1 kg")
    content = export_draft_csv(table, "=2+2", "@formula", None, 25)
    result = next(csv.DictReader(io.StringIO(content)))
    assert result["id_persona"] == "'=2+2"
    assert result["modelo_inbody"] == "'@formula"
