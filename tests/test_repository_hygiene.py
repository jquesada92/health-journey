"""Regresión: no versionar entornos virtuales ni archivos .env."""
from pathlib import Path, PurePosixPath
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV_FOLDERS = {".venv", "venv", "env", "ENV", "virtualenv"}


def test_gitignore_excludes_environment_and_secrets():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for pattern in (".venv/", "venv/", "env/", "ENV/", ".env", ".env.*", "*.env"):
        assert pattern in ignore, f"Falta exclusión: {pattern}"
    assert "!.env.example" not in ignore


def test_git_does_not_track_environment_files():
    try:
        result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False)
    except FileNotFoundError:
        pytest.skip("Git no está instalado en este entorno")
    if result.returncode != 0:
        pytest.skip("Prueba de tracked files solo aplicable a un checkout Git")
    tracked = [name.decode("utf-8", errors="replace") for name in result.stdout.split(b"\x00") if name]
    forbidden = []
    for name in tracked:
        parts = PurePosixPath(name).parts
        leaf = parts[-1]
        if any(part in ENV_FOLDERS for part in parts[:-1]) or leaf == ".env" or leaf.startswith(".env.") or leaf.endswith(".env") or ".env." in leaf:
            forbidden.append(name)
    assert not forbidden, f"Archivos de entorno versionados: {forbidden[:20]}"
