#!/usr/bin/env bash
# Run Health Journey locally with optional AI document-layout detection.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

MODE="${1:---ai}"
if [[ "$MODE" != "--ai" && "$MODE" != "--ocr-only" ]]; then
  echo "Uso: ./run_local_ai.sh [--ai|--ocr-only]" >&2
  exit 2
fi
for f in app.py requirements.txt requirements-ai.txt; do
  [[ -f "$f" ]] || { echo "Falta $f. Ejecuta desde el repositorio." >&2; exit 1; }
done
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
PY=".venv/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt
if [[ "$MODE" == "--ai" ]]; then
  echo "Instalando detector experimental PaddleOCR / PP-DocLayout-S..."
  if ! "$PY" -m pip install -r requirements-ai.txt; then
    echo "No se pudo instalar el runtime IA en este sistema." >&2
    echo "Prueba ./run_local_ai.sh --ocr-only; revisa la compatibilidad de PaddlePaddle." >&2
    exit 1
  fi
  # Validate import before launching; model weights may download on first use.
  if ! "$PY" -c 'from paddleocr import LayoutDetection; print("LayoutDetection disponible")'; then
    echo "No se puede importar LayoutDetection en este entorno." >&2
    echo "Prueba ./run_local_ai.sh --ocr-only." >&2
    exit 1
  fi
  export ENABLE_AI_SECTION_OCR=1
else
  export ENABLE_AI_SECTION_OCR=0
fi
export ENABLE_PERSISTENCE=0
export ENABLE_ANONYMOUS_DEMO=0
echo "Modo: $MODE | http://localhost:${PORT:-7860}"
echo "No habilites Neon ni cargues documentos personales en un Space público."
echo "Detener con Ctrl+C"
exec "$PY" app.py
