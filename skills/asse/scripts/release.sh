#!/usr/bin/env bash
# Release end-to-end: bumpea versión, publica en PyPI, espera, publica en npm.
# Uso: scripts/release.sh 0.2.0
#      scripts/release.sh 0.2.0 --test   (PyPI a test.pypi.org, npm con --dry-run)
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Uso: $0 <version> [--test]" >&2
  exit 1
fi

VERSION="$1"
TEST_MODE=""
if [ "${2:-}" = "--test" ]; then
  TEST_MODE="--test"
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "═══ 1/4  Bump versión a $VERSION"
"$ROOT/scripts/bump.sh" "$VERSION"

echo
echo "═══ 2/4  Publicar en PyPI"
if [ -n "$TEST_MODE" ]; then
  "$ROOT/scripts/publish-pypi.sh" --test
else
  "$ROOT/scripts/publish-pypi.sh"
fi

echo
echo "═══ 3/4  Esperar propagación de PyPI (30s)"
echo "(el postinstall de npm hace 'pip install asse-cli==$VERSION', necesita estar disponible)"
sleep 30

echo
echo "═══ 4/4  Publicar en npm"
if [ -n "$TEST_MODE" ]; then
  "$ROOT/scripts/publish-npm.sh" --dry-run
else
  "$ROOT/scripts/publish-npm.sh"
fi

echo
echo "✓ Release $VERSION completo"
