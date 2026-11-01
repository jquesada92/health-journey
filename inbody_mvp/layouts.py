"""Spatial OCR parser for the InBody 580 sheet layout.

Values are candidates tied to fixed cells, not axis ticks or reference ranges.
Coordinates are normalized and all candidates require human verification.
Never upload patient source documents to this repository.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re


@dataclass(frozen=True)
class Token:
    text: str
    x: float
    y: float
    w: float
    h: float
    confidence: float = 1.0

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2


def normalize_detections(detections, width, height):
    if not width or not height:
        return []
    tokens = []
    for item in detections:
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            continue
        points, value = item[:2]
        if not isinstance(points, (list, tuple)) or len(points) < 4:
            continue
        try:
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
            x, y = min(xs), min(ys)
            w, h = max(xs) - x, max(ys) - y
            confidence = float(item[2]) if len(item) > 2 else 1.0
        except (ValueError, TypeError, IndexError):
            continue
        if w > 0 and h > 0 and str(value).strip():
            tokens.append(Token(str(value).strip(), x / width, y / height,
                                w / width, h / height, confidence))
    return tokens


def tokens_to_text(tokens):
    groups = []
    for t in sorted(tokens, key=lambda a: (a.cy, a.cx)):
        if groups and abs(groups[-1][0].cy - t.cy) < .005:
            groups[-1].append(t)
        else:
            groups.append([t])
    return "\n".join(" ".join(t.text for t in sorted(group, key=lambda a: a.x))
                     for group in groups)


def extract_header_exam_timestamp(detections, width, height):
    """Read the exam clock from header OCR boxes, not flattened OCR lines.

    On InBody sheets the label may share its text row with Gender/Género.
    The date and clock often appear beneath it as separate detections,
    including a trailing dot in "04.10.2026. 10:04". Limit the search to
    the exam-date column in the TOP header: never inspect DOB or graph rows.
    """
    tokens = normalize_detections(detections, width, height)
    # OCR can split "Fecha / Hora del test" into multiple boxes. Reconstruct
    # only the label row, never the value row or a full-page text stream.
    top = [t for t in tokens if .015 <= t.cy <= .19]
    label_re = re.compile(
        r"(?:fecha\s*/\s*hora(?:\s+(?:del|de)\s+(?:test|examen|prueba))?"
        r"|test\s+date\s*/\s*time|date\s*/\s*time)", re.I
    )
    label = None
    label_row = [t for t in top if t.cy < .105]
    for candidate in sorted(label_row, key=lambda t: (t.cy, t.cx)):
        if label_re.search(candidate.text):
            label = candidate
            break
    if label is None:
        for candidate in sorted(label_row, key=lambda t: (t.cy, t.cx)):
            if not re.search(r"^(fecha|test|date)$", candidate.text, re.I):
                continue
            nearby = sorted(
                (t for t in label_row
                 if abs(t.cy - candidate.cy) <= .008
                 and candidate.x <= t.x <= candidate.x + .22),
                key=lambda t: t.x,
            )
            if label_re.search(" ".join(t.text for t in nearby)):
                label = candidate
                break
    if label is None:
        return None
    # The date may begin left of the printed label. Exclude the DOB column,
    # and never use values on an unrelated baseline.
    min_x = max(.45, label.cx - .15)
    header = [t for t in top
              if t.cx >= min_x
              and label.cy + .008 <= t.cy <= min(.22, label.cy + .085)]

    date_re = re.compile(
        r"(?<!\d)(\d{4}[/.-]\d{1,2}[/.-]\d{1,2}|"
        r"\d{1,2}[/.-]\d{1,2}[/.-]\d{4})(?!\d)"
    )
    time_re = re.compile(r"(?<!\d)(\d{1,2}:\d{2}(?::\d{2})?)(?!\d)")

    dates = []
    clocks = []
    # The DOB column ends to the left of this ROI. The exam column starts
    # near 0.47 x and the time can extend to roughly 0.70 x.
    for token in header:
        date_match = date_re.search(token.text)
        if date_match:
            dates.append((token, date_match.group(1)))
        time_match = time_re.search(token.text)
        if time_match:
            clocks.append((token, time_match.group(1)))
    for date_token, raw_date in dates:
        parts = re.split(r"[/.-]", raw_date)
        try:
            if len(parts[0]) == 4:
                year, month, day = map(int, parts)
            else:
                day, month, year = map(int, parts)
            exam_date = datetime(year, month, day)
        except ValueError:
            continue
        # Pair only values on the same printed baseline. Do not associate
        # the exam date with unrelated times found elsewhere on the page.
        for clock_token, raw_clock in clocks:
            if abs(date_token.cy - clock_token.cy) > .014:
                continue
            try:
                clock = datetime.strptime(
                    raw_clock, "%H:%M:%S" if raw_clock.count(":") == 2 else "%H:%M"
                )
                return exam_date.replace(
                    hour=clock.hour, minute=clock.minute, second=clock.second
                ).isoformat(timespec="seconds")
            except ValueError:
                continue
    return None


@dataclass(frozen=True)
class Cell:
    metric: str
    label: str
    unit: str
    category: str
    dimension: str
    rect: tuple[float, float, float, float]
    segment: str | None = None


def cell(metric, label, unit, category, dimension, x0, y0, x1, y1, segment=None):
    return Cell(metric, label, unit, category, dimension, (x0, y0, x1, y1), segment)


CELLS = [
    cell("total_body_water", "Total Body Water", "L", "agua", "volumen", .175,.145,.335,.167),
    cell("protein_mass", "Protein", "kg", "composicion", "masa", .175,.171,.30,.193),
    cell("mineral_mass", "Minerals", "kg", "composicion", "masa", .175,.195,.30,.215),
    cell("body_fat_mass", "Body Fat Mass", "kg", "grasa", "masa", .175,.216,.30,.24),
    cell("weight", "Weight", "kg", "peso", "masa", .551,.177,.615,.205),
    cell("skeletal_muscle_mass", "SMM", "kg", "musculo", "masa", .379,.327,.44,.344),
    cell("body_fat_mass", "Body Fat Mass", "kg", "grasa", "masa", .345,.357,.41,.372),
    cell("bmi", "BMI", "kg/m²", "composicion", "indice", .365,.421,.425,.44),
    cell("body_fat_percentage", "PBF", "%", "grasa", "porcentaje", .355,.45,.425,.469),
    cell("inbody_score", "InBody Score", "points", "evaluacion", "puntuacion", .75,.158,.83,.18),
    cell("target_weight", "Target Weight", "kg", "control", "masa", .79,.349,.845,.364),
    cell("weight_control", "Weight Control", "kg", "control", "masa", .787,.364,.842,.383),
    cell("fat_control", "Fat Control", "kg", "control", "masa", .787,.381,.842,.40),
    cell("muscle_control", "Muscle Control", "kg", "control", "masa", .787,.399,.842,.415),
    cell("intracellular_water", "Intracellular Water", "L", "agua", "volumen", .785,.427,.839,.444),
    cell("extracellular_water", "Extracellular Water", "L", "agua", "volumen", .785,.442,.839,.461),
    cell("fat_free_mass", "Fat Free Mass", "kg", "masa_libre_grasa", "masa", .785,.463,.839,.480),
    cell("basal_metabolic_rate", "Basal Metabolic Rate", "kcal", "metabolismo", "energia", .783,.477,.839,.495),
    cell("waist_hip_ratio", "Waist-Hip Ratio", "ratio", "composicion", "razon", .785,.491,.839,.509),
    cell("waist_circumference", "Waist Circumference", "cm", "antropometria", "longitud", .785,.508,.839,.525),
    cell("visceral_fat_level", "Visceral Fat Level", "level", "grasa", "nivel", .785,.524,.839,.541),
    cell("bone_mineral_content", "Bone Mineral Content", "kg", "composicion", "masa", .785,.540,.839,.558),
    cell("recommended_calorie_intake", "Recommended calorie intake", "kcal", "metabolismo", "energia", .785,.553,.84,.571),
    cell("ecw_tbw_ratio", "ECW Ratio", "ratio", "hidratacion", "razon", .29,.727,.375,.744),
    cell("phase_angle", "Overall Phase Angle", "°", "bioimpedancia", "angulo", .577,.721,.64,.742),
]
for segment, top, bottom in (
    ("right_arm", .521,.536), ("left_arm", .551,.566),
    ("trunk", .584,.599), ("right_leg", .616,.631), ("left_leg", .649,.663)
):
    CELLS.extend([
        cell("segmental_lean_mass", "Segmental Lean Mass", "kg", "masa_libre_grasa", "masa", .29,top+.001,.435,top+.014,segment),
        cell("segmental_lean_reference_percentage", "Segmental Lean vs ideal", "%", "masa_libre_grasa", "porcentaje_referencia", .294,bottom-.006,.45,bottom+.008,segment),
        cell("segmental_ecw_ratio", "Segmental ECW Ratio", "ratio", "hidratacion", "razon", .51,top-.002,.583,top+.012,segment),
        cell("phase_angle", "Segmental Phase Angle", "°", "bioimpedancia", "angulo", .579,top-.003,.635,top+.011,segment),
    ])
for segment, y in (
    ("right_arm", .614), ("left_arm", .631), ("trunk", .647),
    ("right_leg", .664), ("left_leg", .680)
):
    CELLS.extend([
        cell("segmental_fat_mass", "Segmental Fat Mass", "kg", "grasa", "masa", .743,y-.009,.808,y+.009,segment),
        cell("segmental_fat_reference_percentage", "Segmental Fat vs ideal", "%", "grasa", "porcentaje_referencia", .86,y-.009,.94,y+.009,segment),
    ])
for segment, y in (
    ("right_arm", .719), ("left_arm", .737), ("trunk", .754),
    ("right_leg", .770), ("left_leg", .786)
):
    CELLS.append(cell("segmental_extracellular_water", "Segmental Extracellular Water",
                      "L", "agua", "volumen", .785,y-.008,.845,y+.009,segment))


def numeric(text):
    value = text.strip().replace("−", "-").replace("–", "-")
    if "~" in value or "…" in value or ".." in value:
        return None
    value = re.sub(r"\s*(?:kg|kcal|cm|l|L|°|%|points?)\s*$", "", value, flags=re.I).strip(" ()")
    if not re.fullmatch(r"[+-]?\d{1,5}(?:[.,]\d{1,3})?", value):
        return None
    return float(value.replace(",", "."))


def selected_value(tokens, spec):
    x0,y0,x1,y1 = spec.rect
    cx,cy = (x0+x1)/2, (y0+y1)/2
    options = []
    for token in tokens:
        if not (x0 <= token.cx <= x1 and y0 <= token.cy <= y1):
            continue
        value = numeric(token.text)
        if spec.metric == "inbody_score" and re.fullmatch(r"\d{1,3}\s*/\s*100(?:\s*Points)?",token.text,re.I):
            value = float(token.text.split("/")[0])
        if value is None:
            continue
        if spec.metric in {"weight_control","fat_control"}:
            minus = any(t.text.strip() in {"-", "−"} and abs(t.cy-token.cy)<.006 and
                        0 < token.cx-t.cx < .035 for t in tokens)
            if minus:
                value = -abs(value)
            elif not token.text.strip().startswith(("-", "−")):
                continue
        if spec.metric == "segmental_lean_mass":
            if "." not in token.text and "," not in token.text:
                continue
            if spec.segment == "trunk" and value < 12:
                continue
        if spec.metric in {"phase_angle","skeletal_muscle_mass","body_fat_percentage"}:
            if "." not in token.text and "," not in token.text:
                continue
        if spec.metric.endswith("reference_percentage") and not 40 <= value <= 300:
            continue
        if spec.metric == "phase_angle" and not 0 < value < 25:
            continue
        if spec.metric.endswith("ecw_ratio") and not .2 < value < .8:
            continue
        options.append((abs(token.cx-cx)*.6+abs(token.cy-cy),-token.confidence,value,token.text))
    if not options:
        return None
    options.sort()
    return options[0][2], options[0][3]


def extract_inbody580(detections, width, height):
    tokens = normalize_detections(detections, width, height)
    heading = " ".join(t.text for t in sorted(
        (t for t in tokens if t.cy < .085 and .49 < t.cx < .67),
        key=lambda t:(t.cy,t.cx)))
    if not re.search(r"in\s*body\s*\[?\s*580\s*\]?", heading, re.I):
        return [], {}
    rows, seen = [], set()
    for spec in CELLS:
        selection = selected_value(tokens, spec)
        key = spec.metric, spec.segment
        if selection is None or key in seen:
            continue
        seen.add(key)
        value, source_token = selection
        rows.append(dict(original_label=spec.label,variable_medida=spec.metric,
                         categoria=spec.category,dimension=spec.dimension,
                         unidad_medida=spec.unit,valor_medida=value,segmento=spec.segment,
                         frecuencia_khz=None,fuente="ocr_layout_inbody580",
                         texto_fuente=source_token,revisar=True))
    top = " ".join(t.text for t in tokens if t.cy < .115)
    metadata = {"modelo_inbody":"InBody 580"}
    match = re.search(r"(?<!\d)\d-\d{2,5}-\d{3,6}(?!\d)",top)
    if match:
        metadata["id_persona"] = match.group()
    def from_roi(x0,x1,y0,y1):
        return " ".join(t.text for t in sorted(tokens,key=lambda v:(v.cy,v.cx))
                        if x0 < t.cx < x1 and y0 < t.cy < y1)
    def date_match(text):
        match = re.search(r"(?<!\d)(\d{2}[./]\d{2}[./]\d{4})(?!\d)",text)
        return match.group(1) if match else None
    metadata["dob_raw"] = date_match(from_roi(.325,.46,.09,.116))
    date_line = from_roi(.47,.64,.082,.116)
    metadata["exam_date_raw"] = date_match(date_line)
    time_match = re.search(r"(?<!\d)(\d{1,2}:\d{2})(?!\d)",date_line)
    if time_match:
        metadata["exam_time_raw"] = time_match.group(1)
    age_match = re.search(r"\b(\d{1,3})\b",from_roi(.33,.40,.082,.103))
    if age_match:
        metadata["age_raw"] = int(age_match.group(1))
    return rows, metadata
