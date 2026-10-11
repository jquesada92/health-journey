#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

for required_file in app.py README.md requirements.txt; do
  if [[ ! -f "$required_file" ]]; then
    echo "Falta $required_file en la carpeta del proyecto." >&2
    exit 1
  fi
done

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements.txt
echo "Abre http://localhost:7860 · Detener: Ctrl+C"
exec .venv/bin/python app.py
