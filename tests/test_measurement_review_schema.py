"""Keep measurement review columnar schema consistent and decimal precision safe."""
from pathlib import Path
from types import SimpleNamespace
from inbody_mvp.review import REVIEW_COLUMNS, review_table

def test_frequency_not_separate_column_and_segment_frequencies_distinct():
    measures = [
        SimpleNamespace(original_label="Impedancia",variable_medida="impedance",
            categoria="bioimpedancia",dimension="resistencia",segmento="left_arm",
            frecuencia_khz=f,unidad_medida="Ω",valor_medida=v,pagina=1,fuente="ocr")
        for f,v in ((20,321.5),(100,286.4))]
    table = review_table(SimpleNamespace(medidas=measures))
    assert "frecuencia_khz" not in REVIEW_COLUMNS
    assert "frecuencia_khz" not in table.columns
    assert table.variable_medida.tolist() == ["impedance__20khz", "impedance__100khz"]

def test_review_preserves_decimal_number():
    measure = SimpleNamespace(original_label="Pierna izquierda",variable_medida="segmental_lean_mass",
        categoria="masa_libre_grasa",dimension="masa",segmento="left_leg",
        frecuencia_khz=None,unidad_medida="kg",valor_medida=8.20,pagina=1,fuente="ocr")
    row = review_table(SimpleNamespace(medidas=[measure])).iloc[0]
    assert row.valor_medida == 8.2
    assert row.valor_medida != 8

def test_gradio_table_column_types_match_column_count():
    source=Path("app.py").read_text()
    assert 'datatype=["str", "str", "str", "str", "str", "str", "number", "number", "str"]' in source
    assert "static_columns=[0, 7, 8]" in source
