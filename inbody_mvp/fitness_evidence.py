"""Verified, limited scientific reference set for the Gemini fitness coach.

References are deliberately curated rather than model-generated. They are
public research references, NOT the user's health records. This module does
not search the web, send queries to a new provider, or claim exhaustive RAG.
Update bibliographic entries only after checking original publication metadata.
"""
from __future__ import annotations

import re
import unicodedata

SCIENTIFIC_REFERENCES = (
    {
        "id": "ACSM-2026",
        "title": "Resistance Training Prescription for Muscle Function, Hypertrophy, and Physical Performance in Healthy Adults: An Overview of Reviews",
        "organization": "American College of Sports Medicine",
        "year": 2026,
        "type": "Posicionamiento oficial; revisión de revisiones de ensayos clínicos",
        "url": "https://pubmed.ncbi.nlm.nih.gov/41843416/",
        "doi": "10.1249/MSS.0000000000003897",
        "summary": (
            "En adultos sanos, el entrenamiento progresivo de fuerza mejora fuerza, tamaño y función. "
            "La dosis depende del objetivo: cargas mayores favorecen fuerza; más series "
            "semanales tienden a favorecer hipertrofia. La revisión no establece una "
            "receta idéntica ni un volumen óptimo exacto para todas las personas."
        ),
        "topics": ("hipertrofia", "fuerza", "programacion"),
    },
    {
        "id": "RECOVERY-2024",
        "title": "The Importance of Recovery in Resistance Training Microcycle Construction",
        "organization": "Revisión científica de recuperación entre sesiones",
        "year": 2024,
        "type": "Revisión de investigaciones sobre recuperación y entrenamiento de resistencia",
        "url": "https://pubmed.ncbi.nlm.nih.gov/38689583/",
        "doi": "",
        "summary": (
            "El entrenamiento hasta el fallo y los volúmenes altos pueden aumentar la "
            "necesidad de recuperación, con elevada variación entre individuos. "
            "Conviene individualizar la distribución del trabajo y observar la "
            "respuesta al programa; no existe un tiempo fijo universal."
        ),
        "topics": ("recuperacion", "programacion"),
    },
    {
        "id": "BIA-2024",
        "title": "Reliability, biological variability, and accuracy of multi-frequency bioelectrical impedance analysis for measuring body composition components",
        "organization": "Estudio metodológico de bioimpedancia multifrecuencia (InBody 770)",
        "year": 2024,
        "type": "Estudio de validación y repetibilidad; muestra pequeña y equipo concreto",
        "url": "https://pubmed.ncbi.nlm.nih.gov/39691170/",
        "doi": "",
        "summary": (
            "Las mediciones repetidas de bioimpedancia bajo condiciones controladas "
            "pueden ser consistentes, pero existen variabilidad biológica y sesgo "
            "frente a métodos de referencia. El resultado depende de equipo y protocolo; "
            "no demuestra directamente cambios reales de músculo ni grasa."
        ),
        "topics": ("composicion",),
    },
    {
        "id": "WHO-2020",
        "title": "World Health Organization 2020 guidelines on physical activity and sedentary behaviour",
        "organization": "Organización Mundial de la Salud",
        "year": 2020,
        "type": "Guía de salud pública basada en revisiones de evidencia",
        "url": "https://pubmed.ncbi.nlm.nih.gov/33239350/",
        "doi": "10.1136/bjsports-2020-102955",
        "summary": (
            "Para adultos en general se recomiendan 150-300 minutos por semana "
            "de actividad aeróbica moderada, o 75-150 de actividad intensa, "
            "además de fortalecimiento de los principales grupos musculares "
            "al menos dos días por semana. Son metas de salud pública, no una "
            "prescripción individual de rendimiento."
        ),
        "topics": ("resistencia", "salud"),
    },
    {
        "id": "ISSN-2017",
        "title": "International Society of Sports Nutrition Position Stand: protein and exercise",
        "organization": "International Society of Sports Nutrition",
        "year": 2017,
        "type": "Posicionamiento científico sobre proteína y ejercicio",
        "url": "https://pubmed.ncbi.nlm.nih.gov/28642676/",
        "doi": "10.1186/s12970-017-0177-8",
        "summary": (
            "Para muchos adultos sanos físicamente activos, el posicionamiento "
            "considera suficiente en términos generales una ingesta proteica "
            "diaria de 1,4 a 2,0 g/kg para apoyar la adaptación al entrenamiento. "
            "No es un objetivo universal ni una prescripción para personas con "
            "restricciones médicas o nutricionales."
        ),
        "topics": ("nutricion", "recuperacion"),
    },
    {
        "id": "SLEEP-2015",
        "title": "Recommended Amount of Sleep for a Healthy Adult: A Joint Consensus Statement of the American Academy of Sleep Medicine and Sleep Research Society",
        "organization": "AASM y Sleep Research Society",
        "year": 2015,
        "type": "Consenso basado en evidencia sobre sueño y salud general",
        "url": "https://pubmed.ncbi.nlm.nih.gov/25979105/",
        "doi": "10.5664/jcsm.4758",
        "summary": (
            "El consenso recomienda dormir regularmente al menos siete horas "
            "por noche para promover la salud general de adultos. No demuestra "
            "que una duración concreta garantice recuperación muscular o hipertrofia."
        ),
        "topics": ("sueno", "recuperacion"),
    },
    {
        "id": "FAILURE-2026",
        "title": "Effects of resistance training performed to repetition non-failure on exercise performance in healthy adults: a systematic review and meta-analysis",
        "organization": "Revisión sistemática y metaanálisis de entrenamiento al fallo",
        "year": 2026,
        "type": "Metaanálisis de 20 estudios en adultos sanos",
        "url": "https://pubmed.ncbi.nlm.nih.gov/42410632/",
        "doi": "10.1186/s13102-026-01861-z",
        "summary": (
            "En los ensayos analizados, entrenar sin llegar al fallo muscular "
            "tuvo resultados comparables al fallo para hipertrofia, resistencia "
            "muscular y potencia, con posibles ventajas pequeñas para fuerza "
            "dinámica. Las conclusiones dependen de población y protocolo."
        ),
        "topics": ("hipertrofia", "fuerza", "programacion"),
    },
)

TOPIC_TERMS = {
    "hipertrofia": (
        "hipertrof", "muscul", "masa magra", "masa muscular", "crecimiento",
        "hypertrophy", "muscle growth",
    ),
    "fuerza": (
        "fuerza", "strength", "1rm", "carga", "peso levantad",
        "repeticion maxima", "powerlifting",
    ),
    "resistencia": (
        "resistencia", "cardio", "aerobic", "aerobic", "aerobica",
        "running", "correr", "carrera", "endurance", "vo2",
    ),
    "composicion": (
        "inbody", "bioimped", "impedancia", "grasa", "adipos", "fat mass",
        "composicion", "porcentaje graso", "agua corporal", "musculo esquele",
    ),
    "recuperacion": (
        "recuper", "fatiga", "descans", "agotamiento", "sobrecarga",
        "soreness", "doms", "recovery", "lesion", "dolor muscular",
    ),
    "nutricion": (
        "proteina", "comida", "nutri", "macro", "caloria", "dieta",
        "alimentacion", "protein",
    ),
    "sueno": ("dormir", "sueno", "sleep", "insomnio", "horas de cama"),
    "programacion": (
        "volumen", "frecuencia", "series", "periodiza", "rutina",
        "entrenamiento", "fallo", "rir", "rpe", "repeticiones",
    ),
    "salud": ("salud general", "actividad fisica", "sedentar"),
}


def _normalize(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", str(value or "").lower())
        if not unicodedata.combining(char)
    )


def select_scientific_references(question: str, objectives: str = "", *, limit: int = 4) -> list[dict]:
    """Select a few relevant VERIFIED publications without external lookup.

    The user's question ranks above optional goals. Unknown topics yield no
    invented reference. The selected catalog entries are sent verbatim as
    citation data, not represented as a live research search.
    """
    if not 1 <= limit <= len(SCIENTIFIC_REFERENCES):
        raise ValueError("Límite de referencias inválido.")
    question_text, objective_text = _normalize(question), _normalize(objectives)
    scores = {}
    for source in SCIENTIFIC_REFERENCES:
        score = 0
        for topic in source["topics"]:
            terms = TOPIC_TERMS[topic]
            if any(term in question_text for term in terms):
                score += 3
            elif any(term in objective_text for term in terms):
                score += 1
        if score:
            scores[source["id"]] = score
    ranked = sorted(
        (source for source in SCIENTIFIC_REFERENCES if source["id"] in scores),
        key=lambda source: (
            -scores[source["id"]], -source["year"],
        ),
    )
    return [dict(ref) for ref in ranked[:limit]]


def format_reference_footer(references: list[dict]) -> str:
    """Append trustworthy URLs from code, never model-invented citations."""
    if not references:
        return ""
    lines = [
        "",
        "**Referencias científicas disponibles para este análisis** "
        "(bibliografía de apoyo, no prueba de que cada recomendación esté "
        "respaldada por cada estudio):",
    ]
    for source in references:
        lines.append(
            f"- [{source['id']}] {source['organization']} "
            f"({source['year']}). [Publicación]({source['url']})"
        )
    return "\n".join(lines)
