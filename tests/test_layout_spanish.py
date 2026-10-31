"""Fixtures contain made-up values/identifiers; never commit patient images."""
from io import BytesIO
from PIL import Image
from inbody_mvp.layouts_es import extract_spanish_silhouette
from inbody_mvp.extractor import extract_document


def boxes(*items):
    data=[]
    for text,x,y in items:
        xx,yy=x*1000,y*1400
        data.append(([[xx-12,yy-6],[xx+12,yy-6],[xx+12,yy+6],[xx-12,yy+6]],text,.97))
    return data


def fixture():
    return boxes(
        ('Análisis de Magro por Segmentos',.20,.565),
        ('Análisis de Grasa Segmental',.46,.566),
        ('Impedancia',.74,.735),
        ('Puntuación InBody',.72,.14),
        ('ZZ00003456',.115,.090), ('24.03.2025',.51,.092), ('14:20',.577,.092),
        ('32',.345,.092),
        ('44.7',.49,.159),('12.2',.49,.179),('3.92',.49,.200),('13.1',.49,.227),('75.1',.49,.247),
        ('35.2',.420,.368),('27.6',.385,.488),('18.5',.357,.516),
        ('4.12kg',.116,.606),('133.5%',.116,.625),('4.06kg',.255,.606),('134.1%',.255,.625),
        ('29.8kg',.179,.656),('122.2%',.179,.679),('8.33kg',.116,.708),('98.3%',.116,.728),
        ('8.31kg',.254,.708),('99.3%',.254,.728),
        ('0.8kg',.416,.606),('89.5%',.416,.627),('0.7kg',.550,.606),('91.2%',.550,.627),
        ('7.8kg',.485,.657),('201.1%',.485,.681),('1.9kg',.417,.710),('118.5%',.417,.731),
        ('2.0kg',.552,.710),('121.7%',.552,.731),
        ('87/100',.778,.170),('239.5',.751,.767),('237.1',.791,.767),('20.4',.835,.767),('254.1',.874,.767),('261.6',.913,.767),
        ('207.5',.751,.779),('205.1',.791,.779),('16.9',.835,.779),('218.1',.874,.779),('228.5',.913,.779),
        ('200',.385,.35),('170',.34,.35),('26.01.25',.43,.945),('75.0',.418,.854)
    )


def test_distinct_weight_and_segmental_categories():
    rows, metadata=extract_spanish_silhouette(fixture(),1000,1400)
    values={(r['variable_medida'],r['segmento'],r['frecuencia_khz']):r['valor_medida'] for r in rows}
    assert values['inbody_score',None,None]==87.0
    assert values['weight',None,None]==75.1
    assert values['skeletal_muscle_mass',None,None]==35.2
    assert values['segmental_lean_mass','left_arm',None]==4.12
    assert values['segmental_lean_reference_percentage','left_arm',None]==133.5
    assert values['segmental_fat_mass','left_arm',None]==0.8
    assert values['segmental_fat_reference_percentage','left_arm',None]==89.5
    assert values['impedance','right_arm',20]==239.5
    assert values['impedance','right_arm',100]==207.5
    assert values['impedance','left_leg',100]==228.5
    assert values['impedance','trunk',100]==16.9
    assert metadata['exam_date_raw']=='24.03.2025'
    assert metadata['age_raw']==32
    assert 'modelo_inbody' not in metadata
    assert 170 not in values.values() and 200 not in values.values()


def test_non_matching_layout_does_not_extract_by_fixed_coordinate():
    rows,metadata=extract_spanish_silhouette(boxes(('InBody580',.55,.06),('75.1',.49,.247)),1000,1400)
    assert (rows,metadata)==([], {})


def test_full_flow_jpeg_uses_reviewable_candidates():
    stream=BytesIO();Image.new('RGB',(1000,1400),'white').save(stream,format='JPEG')
    result=extract_document('synthetic.jpg',stream.getvalue(),ocr=lambda image:fixture())
    assert result.timestamp=='2025-03-24T14:20:00'
    assert result.edad==32 and result.origen_edad=='reportada_no_calculada'
    assert result.modelo_inbody is None
    assert all(x.revisar for x in result.medidas)
    assert any(x.variable_medida=='impedance' and x.frecuencia_khz==100 for x in result.medidas)
    assert all(x.valor_medida!=170 for x in result.medidas)
    assert any('historial' in x.lower() for x in result.advertencias)

def test_rejects_incomplete_bmi_and_score_ocr_fragments():
    data=fixture()+boxes(('7',.778,.170),('7.0',.385,.488))
    rows,_=extract_spanish_silhouette(data,1000,1400)
    vals={r['variable_medida']:r['valor_medida'] for r in rows if not r['segmento']}
    assert vals.get('inbody_score')==87.0
    assert vals.get('bmi')==27.6
