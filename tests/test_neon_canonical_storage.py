"""Canonical persistence contract: one measurement, one value, one unit."""
import ast
from pathlib import Path
from inbody_mvp.storage import StoredMeasurement

def test_stored_measurement_has_no_frequency_column():
    assert "frecuencia_khz" not in StoredMeasurement.model_fields
    measurement=StoredMeasurement(
        original_label="Ángulo de fase",variable_medida="phase_angle__left_leg__50khz",
        unidad_medida="°",valor_medida=6.1,segmento="left_leg")
    assert measurement.valor_medida == 6.1
    assert measurement.unidad_medida == "°"

def test_insert_no_frequency_column():
    code=Path("inbody_mvp/storage.py").read_text()
    assert "segmento, frecuencia_khz," not in code
    assert ":segmento, :frecuencia_khz," not in code
    ast.parse(code)
