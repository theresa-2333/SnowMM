"""Exercise the frozen application with isolated, disposable user data."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    name = "SnowMM-Diagnostic" if "--diagnostic" in sys.argv else "SnowMM"
    executable = ROOT / "dist" / name / f"{name}.exe"
    report = ROOT / "dist" / "release-self-test.json"
    with tempfile.TemporaryDirectory(prefix="snowmm-frozen-") as home:
        environment = dict(os.environ, SNOWMM_HOME=home, QT_QPA_PLATFORM="offscreen")
        result = subprocess.run([str(executable), "--self-test", str(report)], env=environment,
                                cwd=home, timeout=90, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        result.check_returncode()
    result = json.loads(report.read_text(encoding="utf-8"))
    if not result.get("ok"):
        raise RuntimeError(result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
