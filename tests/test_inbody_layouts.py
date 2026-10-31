"""Synthetic spatial OCR fixtures; never commit real health reports."""
from io import BytesIO

from PIL import Image

from inbody_mvp.extractor import extract_document
from inbody_mvp.layouts import extract_inbody580


def boxes(*values):
    out = []
    for text, x, y in values:
        xx, yy = 1000*x, 1400*y
        out.append(([[xx-12,yy-7],[xx+12,yy-7],[xx+12,yy+7],[xx-12,yy+7]],text,.99))
    return out


def test_layout_detects_cells_and_not_axis_ticks():
    ocr = boxes(
        ("[InBody580]", .58,.056),
        ("72.4",.572,.189), ("115",.347,.549), ("100",.307,.549),
        ("3.66",.404,.56), ("0.375",.538,.558), ("7.0°",.599,.558),
        ("1.8 kg",.77,.680), ("120.3%",.895,.680)
    )
    rows, meta = extract_inbody580(ocr,1000,1400)
    values = {(r["variable_medida"],r["segmento"]):r["valor_medida"] for r in rows}
    assert meta["modelo_inbody"] == "InBody 580"
    assert values["weight",None] == 72.4
    assert values["segmental_lean_mass","left_arm"] == 3.66
    assert values["phase_angle","left_arm"] == 7.0
    assert values["segmental_fat_mass","left_leg"] == 1.8
    assert values["segmental_fat_reference_percentage","left_leg"] == 120.3
    assert 100 not in values.values() and 115 not in values.values()


def test_control_negative_not_inferred_without_minus():
    ocr = boxes(("InBody580",.57,.06),("-",.797,.373),
                ("4.5",.816,.373),("4.5",.816,.387))
    rows, _ = extract_inbody580(ocr,1000,1400)
    assert any(r["variable_medida"] == "weight_control" and
               r["valor_medida"] == -4.5 for r in rows)
    assert not any(r["variable_medida"] == "fat_control" for r in rows)


def test_other_model_does_not_apply_fixed_580_layout():
    rows, metadata = extract_inbody580(boxes(("InBody770",.58,.06),
                                               ("99.9",.572,.189)),1000,1400)
    assert rows == [] and metadata == {}


def test_uploaded_jpg_structured_ocr_passes_through_extractor():
    ocr = boxes(("InBody580",.57,.06),("04.10.2026",.52,.093),
                ("10:04",.59,.093),("02.04.1992",.376,.109),
                ("72.4",.57,.189),("20.2",.389,.458),
                ("7.2°",.599,.526))
    stream = BytesIO()
    Image.new("RGB",(1000,1400),"white").save(stream,format="JPEG")
    result = extract_document("synthetic.jpg",stream.getvalue(),ocr=lambda _:ocr)
    assert result.modelo_inbody == "InBody 580"
    assert result.timestamp == "2026-10-04T10:04:00"
    assert result.edad == 34
    found = {(x.variable_medida,x.segmento):x.valor_medida for x in result.medidas}
    assert found["weight",None] == 72.4
    assert found["body_fat_percentage",None] == 20.2
    assert found["phase_angle","right_arm"] == 7.2
    assert all(row.revisar for row in result.medidas)
