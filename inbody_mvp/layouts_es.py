"""Geometric extraction for the Spanish InBody composition sheet with silhouettes.

This is a cautious, position-based OCR candidate reader, not a universal InBody
model detector. It never infers a machine model from a language/template and it
never imports the history graph into the current exam. Requires human review.
All fixtures must be synthetic and must not include identifying patient data.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any

from .layouts import Token, normalize_detections


@dataclass(frozen=True)
class SpanishCell:
    metric: str
    label: str
    unit: str
    category: str
    dimension: str
    rect: tuple[float, float, float, float]
    segment: str | None = None
    frequency: float | None = None
    bounds: tuple[float, float] | None = None


def cell(metric, label, unit, cat, dim, x, y, dx=.038, dy=.008,
         *, segment=None, frequency=None, bounds=None):
    return SpanishCell(metric,label,unit,cat,dim,(x-dx,y-dy,x+dx,y+dy),segment,frequency,bounds)


# ROI centers are normalized to the full sheet. No chart/history region cells.
CELLS: list[SpanishCell] = [
    cell('total_body_water','Agua Corporal Total','L','agua','volumen',.489,.159,bounds=(0,150)),
    cell('protein_mass','Proteínas','kg','composicion','masa',.488,.179,bounds=(0,60)),
    cell('mineral_mass','Minerales','kg','composicion','masa',.490,.200,bounds=(0,30)),
    cell('body_fat_mass','Masa Grasa Corporal','kg','grasa','masa',.489,.227,bounds=(0,160)),
    cell('weight','Peso','kg','peso','masa',.491,.247,bounds=(0,300)),
    cell('skeletal_muscle_mass','Masa musculoesquelética','kg','musculo','masa',.420,.368,bounds=(0,150)),
    cell('bmi','IMC','kg/m²','composicion','indice',.385,.488,dx=.048,dy=.009,bounds=(12,80)),
    cell('body_fat_percentage','Porcentaje de Grasa Corporal','%','grasa','porcentaje',.357,.516,bounds=(0,100)),
    cell('inbody_score','Puntuación InBody','points','evaluacion','puntuacion',.778,.170,bounds=(20,100)),
    cell('target_weight','Peso objetivo','kg','control','masa',.817,.246,bounds=(0,300)),
    cell('weight_control','Control de peso','kg','control','masa',.814,.261,bounds=(-200,200)),
    cell('fat_control','Control de grasa','kg','control','masa',.814,.278,bounds=(-200,200)),
    cell('muscle_control','Control muscular','kg','control','masa',.814,.295,bounds=(-200,200)),
    cell('waist_hip_ratio','Relación Cintura-Cadera','ratio','composicion','razon',.701,.396,bounds=(.4,2)),
    cell('visceral_fat_level','Nivel de grasa visceral','level','grasa','nivel',.742,.446,bounds=(0,70)),
    cell('fat_free_mass','Masa Libre de Grasa','kg','masa_libre_grasa','masa',.812,.510,bounds=(0,250)),
    cell('basal_metabolic_rate','Tasa metabólica basal','kcal','metabolismo','energia',.817,.526,bounds=(300,6000)),
    cell('waist_circumference','Circunferencia de la cintura','cm','antropometria','longitud',.816,.553,bounds=(25,250)),
    cell('obesity_degree','Grado de obesidad','%','composicion','porcentaje_referencia',.814,.575,bounds=(30,500)),
    cell('smi','MME','kg/m²','composicion','indice',.812,.591,bounds=(1,30)),
    cell('recommended_calorie_intake','Ingesta de calorías recomendada','kcal','metabolismo','energia',.816,.608,bounds=(300,8000)),
]
# Deliberate: a second SMM, PBF, fat mass, WHR, visceral fat level is not
# emitted twice; these appear in multiple print sections on the same sheet.

# Left/right reflect the silhouette labels, not the observer's direction.
LEAN = [
    ('left_arm',.116,.606,.625),
    ('right_arm',.255,.606,.625),
    ('trunk',.179,.656,.679),
    ('left_leg',.116,.708,.728),
    ('right_leg',.254,.708,.728),
]
FAT = [
    ('left_arm',.416,.606,.627),
    ('right_arm',.550,.606,.627),
    ('trunk',.485,.657,.681),
    ('left_leg',.417,.710,.731),
    ('right_leg',.552,.710,.731),
]
for group, mass_key, pct_key, cat in (
    (LEAN,'segmental_lean_mass','segmental_lean_reference_percentage','masa_libre_grasa'),
    (FAT,'segmental_fat_mass','segmental_fat_reference_percentage','grasa'),
):
    for seg,x,ym,yp in group:
        CELLS.extend([
            cell(mass_key,'Análisis segmental', 'kg',cat,'masa',x,ym,dx=.043,dy=.009,segment=seg,bounds=(0,150)),
            cell(pct_key,'Porcentaje frente a referencia segmental','%',cat,
                 'porcentaje_referencia',x,yp,dx=.042,dy=.007,segment=seg,bounds=(0,400)),
        ])

# Impedance array: BD/BI/TR/PD/PI at 20 and 100 kHz, in ohms.
# Treat each frequency and each body segment as a separate measurement.
IMPEDANCE_COLUMNS = [
    ('right_arm',.751),('left_arm',.791),('trunk',.835),
    ('right_leg',.874),('left_leg',.913),
]
for freq,y in ((20,.767),(100,.779)):
    for segment,x in IMPEDANCE_COLUMNS:
        CELLS.append(cell('impedance','Impedancia', 'Ω','bioimpedancia','resistencia',
                          x,y,dx=.021,dy=.006,segment=segment,frequency=freq,
                          bounds=(0.1,3000)))


def _plain(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD',s.casefold())
                   if not unicodedata.combining(c))


def is_spanish_silhouette_sheet(tokens: list[Token]) -> bool:
    """Require multiple distinctive headings to avoid applying a wrong template."""
    top = ' '.join(_plain(t.text) for t in tokens if .10 < t.cy < .80)
    signatures = (
        ('magro', 'segment'),
        ('grasa', 'segment'),
        ('impedancia',),
        ('composicion', 'corporal'),
    )
    matches = sum(all(word in top for word in pattern) for pattern in signatures)
    # Restrict to known overall sheet layout, not 580, and require two signatures.
    header = ' '.join(_plain(t.text) for t in tokens if t.cy < .12)
    return matches >= 2 and 'inbody580' not in header.replace(' ','')


def _number(text: str) -> float | None:
    """A single decimal, optionally followed by a unit; no reference ranges."""
    value = text.strip().replace('−','-').replace('–','-')
    if '~' in value or '…' in value or '..' in value:
        return None
    value = re.sub(r'\s*(?:kg\s*/\s*m[²2]|kg|kcal|cm|l|°|%|[oO]hms?|Ω|puntos?)\s*$',
                   '',value,flags=re.I).strip(' ()')
    if not re.fullmatch(r'[+-]?(?:\d{1,5}(?:[.,]\d{1,3})?|[.,]\d{1,3})',value):
        return None
    try:
        return float(value.replace(',','.'))
    except ValueError:
        return None


def _choose(tokens: list[Token], spec: SpanishCell) -> tuple[float,str] | None:
    x0,y0,x1,y1=spec.rect
    options=[]
    for t in tokens:
        if not x0 <= t.cx <= x1 or not y0 <= t.cy <= y1:
            continue
        val=_number(t.text)
        if spec.metric == "inbody_score":
            score = re.fullmatch(r"\s*(\d{1,3})\s*/\s*100(?:\s*puntos?)?\s*", t.text, re.I)
            if score:
                val = float(score.group(1))
        if spec.metric == 'inbody_score' and val is not None and len(str(int(val))) < 2:
            # Split OCR can return '7' for a printed '87/100'. Reject fragments.
            continue
        if val is None or spec.bounds and not (spec.bounds[0] <= val <= spec.bounds[1]):
            continue
        if spec.metric in ('weight_control','fat_control','muscle_control'):
            minus=any(m.text.strip() in ('-','−','–') and abs(m.cy-t.cy)<.006
                      and 0 < t.cx-m.cx < .035 for m in tokens)
            if minus:
                val=-abs(val)
            # Other signed readings can be positive; don't infer sign.
        options.append((abs(t.cx-(x0+x1)/2)*.8+abs(t.cy-(y0+y1)/2),
                        -t.confidence,val,t.text))
    if not options:
        return None
    options.sort()
    return options[0][2],options[0][3]


def _header(tokens: list[Token], x0,x1,y0,y1) -> str:
    return ' '.join(t.text for t in sorted(tokens,key=lambda t:(t.cy,t.cx))
                    if x0<=t.cx<=x1 and y0<=t.cy<=y1)


def extract_spanish_silhouette(detections: list, width: int, height: int) -> tuple[list[dict],dict[str,Any]]:
    """Return source-backed candidates and metadata, never historical graph values."""
    tokens=normalize_detections(detections,width,height)
    if not is_spanish_silhouette_sheet(tokens):
        return [],{}
    rows=[]; seen=set()
    for spec in CELLS:
        picked=_choose(tokens,spec)
        if picked is None:
            continue
        value,raw=picked
        key=(spec.metric,spec.segment,spec.frequency)
        if key in seen:
            continue
        seen.add(key)
        rows.append(dict(original_label=spec.label,variable_medida=spec.metric,
                         categoria=spec.category,dimension=spec.dimension,
                         unidad_medida=spec.unit,valor_medida=value,
                         segmento=spec.segment,frecuencia_khz=spec.frequency,
                         fuente='ocr_layout_spanish_silhouette',texto_fuente=raw,revisar=True))
    # A generic model cannot be inferred from the sheet's language or footer.
    metadata:dict[str,Any]={'layout':'spanish_silhouette'}
    id_text=_header(tokens,.045,.19,.076,.110)
    match=re.search(r'(?<!\d)(?:[A-Za-z]{2,4}[-_]?)?\d{6,20}(?!\d)',id_text)
    if match:
        metadata['id_persona']=match.group(0)
    # Date + clock may be a single detection or separate tokens.
    date_text=_header(tokens,.465,.63,.077,.107)
    date_match=re.search(r'(?<!\d)\d{2}[./-]\d{2}[./-]\d{4}(?!\d)',date_text)
    if date_match:
        metadata['exam_date_raw']=date_match.group()
    clock_match=re.search(r'(?<!\d)\d{1,2}:\d{2}(?!\d)',date_text)
    if clock_match:
        metadata['exam_time_raw']=clock_match.group()
    age_text=_header(tokens,.315,.38,.075,.107)
    age_match=re.search(r'(?<!\d)\d{1,3}(?!\d)',age_text)
    if age_match:
        metadata['age_raw']=int(age_match.group())
    metadata['warnings']=[
       'Plantilla española con siluetas: mediciones candidatas por coordenadas; revisar todas las cifras.',
       'Los porcentajes segmentales son relativos a referencia, no grasa ni músculo porcentual del segmento.',
       'El gráfico de historial del documento no se importa como evaluaciones independientes.',
       'Modelo de equipo no identificado de manera inequívoca: confirmar manualmente.'
    ]
    return rows,metadata