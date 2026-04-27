const { spawnSync } = require("child_process");

const CANDIDATES = ["python3.13", "python3.12", "python3.11", "python3", "python"];
const MIN_MAJOR = 3;
const MIN_MINOR = 11;

function checkVersion(bin) {
  const r = spawnSync(bin, ["-c", "import sys; print(sys.version_info[0], sys.version_info[1])"], {
    encoding: "utf8",
  });
  if (r.status !== 0) return null;
  const [maj, min] = r.stdout.trim().split(" ").map(Number);
  if (maj > MIN_MAJOR || (maj === MIN_MAJOR && min >= MIN_MINOR)) return { maj, min };
  return null;
}

function resolvePython() {
  for (const bin of CANDIDATES) {
    if (checkVersion(bin)) return bin;
  }
  return null;
}

module.exports = { resolvePython, checkVersion };
