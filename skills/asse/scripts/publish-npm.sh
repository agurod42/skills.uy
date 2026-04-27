#!/usr/bin/env bash
# Publica el wrapper en npm.
# Uso: scripts/publish-npm.sh           (publica de verdad)
#      scripts/publish-npm.sh --dry-run (no sube nada, solo muestra qué pasaría)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/npm"

DRY=()
if [ "${1:-}" = "--dry-run" ]; then
  DRY=(--dry-run)
  echo "→ DRY RUN (no se sube nada)"
fi

# Verificar login
if ! npm whoami >/dev/null 2>&1; then
  echo "No estás logueado en npm. Corré: npm login" >&2
  exit 1
fi

# Verificar que las versiones estén sincronizadas
PY_VER=$(python3 -c "import re,pathlib; m=re.search(r'^version\s*=\s*\"([^\"]+)\"', pathlib.Path('$ROOT/pyproject.toml').read_text(), re.M); print(m.group(1))")
NPM_VER=$(node -p "require('$ROOT/npm/package.json').version")
if [ "$PY_VER" != "$NPM_VER" ]; then
  echo "ERROR: versiones desincronizadas — pyproject=$PY_VER vs npm=$NPM_VER" >&2
  echo "Corré: scripts/bump.sh <version>" >&2
  exit 1
fi

echo "→ Publicando asse-cli@$NPM_VER en npm"
npm publish --access public "${DRY[@]}"

echo "✓ Publicado en npm"
