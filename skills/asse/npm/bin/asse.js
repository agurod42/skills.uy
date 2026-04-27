#!/usr/bin/env node
const { spawnSync } = require("child_process");
const { resolvePython } = require("../scripts/python");

const python = resolvePython();
if (!python) {
  console.error(
    "asse-cli: no se encontró Python 3.11+. Instalalo desde https://www.python.org/downloads/ y reintentá."
  );
  process.exit(1);
}

const result = spawnSync(python, ["-m", "asse_cli.cli", ...process.argv.slice(2)], {
  stdio: "inherit",
});

if (result.error) {
  console.error("asse-cli: falló al ejecutar Python:", result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 1);
