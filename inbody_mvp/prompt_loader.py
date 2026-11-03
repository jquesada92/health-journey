"""Read separately versioned, locally bundled prompts for each Gemini module."""
from pathlib import Path

_PROMPT_FILES = {
    "inbody_extraction": "inbody_extraction.md",
    "fitness_coach": "fitness_coach.md",
}
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    """Only accept a known prompt name; never load user-provided paths."""
    if name not in _PROMPT_FILES:
        raise ValueError("Nombre de prompt desconocido.")
    content = (_PROMPTS_DIR / _PROMPT_FILES[name]).read_text(encoding="utf-8").strip()
    if not content:
        raise RuntimeError(f"Prompt vacío: {name}.")
    return content
