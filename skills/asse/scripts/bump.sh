#!/usr/bin/env bash
# Sincroniza la versión en pyproject.toml y npm/package.json.
# Uso: scripts/bump.sh 0.2.0
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Uso: $0 <version>   (ej: 0.2.0)" >&2
  exit 1
fi

VERSION="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([a-zA-Z0-9.+-]*)?$ ]]; then
  echo "Versión inválida: $VERSION (esperado semver, ej 0.2.0)" >&2
  exit 1
fi

# pyproject.toml
python3 - "$VERSION" "$ROOT/pyproject.toml" <<'PY'
import re, sys, pathlib
version, path = sys.argv[1], pathlib.Path(sys.argv[2])
text = path.read_text()
new = re.sub(r'^version\s*=\s*"[^"]+"', f'version = "{version}"', text, count=1, flags=re.M)
if new == text:
    sys.exit("No se encontró 'version = \"...\"' en pyproject.toml")
path.write_text(new)
PY

# npm/package.json
node -e '
  const fs = require("fs");
  const p = process.argv[1];
  const v = process.argv[2];
  const pkg = JSON.parse(fs.readFileSync(p, "utf8"));
  pkg.version = v;
  fs.writeFileSync(p, JSON.stringify(pkg, null, 2) + "\n");
' "$ROOT/npm/package.json" "$VERSION"

echo "✓ Versión actualizada a $VERSION en pyproject.toml y npm/package.json"
