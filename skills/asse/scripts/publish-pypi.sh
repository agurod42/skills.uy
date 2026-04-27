#!/usr/bin/env bash
# Build + upload a PyPI.
# Uso: scripts/publish-pypi.sh         (sube a pypi.org)
#      scripts/publish-pypi.sh --test  (sube a test.pypi.org)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO_ARGS=()
if [ "${1:-}" = "--test" ]; then
  REPO_ARGS=(--repository testpypi)
  echo "→ Modo TEST: subiendo a test.pypi.org"
fi

echo "→ Limpiando dist/ y build/"
rm -rf dist build src/*.egg-info

echo "→ Asegurando build + twine"
python3 -m pip install --quiet --upgrade build twine

echo "→ Compilando paquete (sdist + wheel)"
python3 -m build

echo "→ Verificando metadata"
python3 -m twine check dist/*

echo "→ Subiendo con twine"
python3 -m twine upload "${REPO_ARGS[@]}" dist/*

echo "✓ Publicado en PyPI"
