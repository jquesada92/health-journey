"""Phase angle is a standalone measured value with degrees, not a frequency row."""
from inbody_mvp.extractor import parse_text
from inbody_mvp.review import review_table, export_draft_csv
from inbody_mvp.storage import prepare_confirmed_exam
import csv
import io

def test_phase_angle_standalone_value_unit_and_frequency_identity():
    text = ("ID: ANON-01\nInBody 580\nBody Composition Analysis\n"
            "Test Date / Time: 31.10.2026. 10:30\n"
            "Phase Angle Left Leg (50 kHz) 6.1 °")
    result = parse_text([(text, "pdf_text")], filename="synthetic.pdf", digest="a"*64)
    table = review_table(result)
    row = table[table.variable_medida.str.startswith("phase_angle")].iloc[0]
    assert row.variable_medida == "phase_angle__50khz"
    assert row.valor_medida == 6.1
    assert row.unidad_medida == "°"
    assert "frecuencia_khz" not in table.columns
    exported = list(csv.DictReader(io.StringIO(
        export_draft_csv(table, "ANON-01", "InBody 580", result.timestamp, 34)
    )))
    assert exported[0]["variable_medida"] == "phase_angle__left_leg__50khz"
    assert exported[0]["unidad_medida"] == "°"
    assert float(exported[0]["valor_medida"]) == 6.1
