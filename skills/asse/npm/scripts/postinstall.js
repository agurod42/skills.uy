const { spawnSync } = require("child_process");
const { resolvePython } = require("./python");

if (process.env.ASSE_SKIP_POSTINSTALL === "1") {
  process.exit(0);
}

const pkg = require("../package.json");
const pyPkg = `asse-cli==${pkg.version}`;

const python = resolvePython();
if (!python) {
  console.error("asse-cli: Python 3.11+ no está instalado.");
  console.error("Instalalo desde https://www.python.org/downloads/ y luego corré:");
  console.error(`  pip install ${pyPkg}`);
  process.exit(0);
}

console.log(`asse-cli: instalando paquete Python "${pyPkg}" con ${python} -m pip ...`);
const r = spawnSync(python, ["-m", "pip", "install", "--user", "--upgrade", pyPkg], {
  stdio: "inherit",
});

if (r.status !== 0) {
  console.error("\nasse-cli: falló `pip install`. Probá manualmente:");
  console.error(`  ${python} -m pip install --user ${pyPkg}`);
  process.exit(0);
}
