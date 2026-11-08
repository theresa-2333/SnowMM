"""Real subprocess fixtures for repair protocol failures; no game data is touched."""

import sys
import unittest
from pathlib import Path

from snowmm.enhanced.repair import RepairService
from tests import test_enhanced as library_tests


class RepairTests(unittest.TestCase):
    setUp = library_tests.LibraryTests.setUp
    tearDown = library_tests.LibraryTests.tearDown
    mod = library_tests.LibraryTests.mod

    def engine(self, body):
        root = self.root / "engine"
        root.mkdir(exist_ok=True)
        (root / "repak.exe").write_bytes(b"test fixture, never executed")
        (root / "assess_mod.py").write_text(
            'import json; print(json.dumps({"risk_level":"fixture", "skm":[]}))', encoding="utf-8"
        )
        (root / "fix_mod.py").write_text(body, encoding="utf-8")
        self.settings.repair_tool = str(root)
        self.settings.repair_python = sys.executable
        return RepairService(self.settings)

    def test_assessment_does_not_change_library(self):
        mod = self.mod()
        before = (Path(mod.folder) / "mod.json").read_bytes()
        service = self.engine("")
        report = service.assess(mod)
        self.assertFalse(report["in_game_verified"])
        self.assertEqual(before, (Path(mod.folder) / "mod.json").read_bytes())

    def test_valid_candidate_preserves_priority_name_and_original(self):
        mod = self.mod()
        service = self.engine("""import sys,json
from pathlib import Path
source=Path(sys.argv[1]); out=Path(sys.argv[sys.argv.index('--outdir')+1])
(out/(source.stem+'_fixed.pak')).write_bytes(b'candidate')
(out/'fix_mod_result.json').write_text(json.dumps([{'converted':1,'padded':0,'risk_level':'fixture'}]))
""")
        old_version, old_bytes = mod.current_version, mod.disk_path.read_bytes()
        result = service.fix(mod)
        self.assertEqual(mod.current_version, old_version)
        self.assertEqual(mod.disk_path.read_bytes(), old_bytes)
        files = mod.files(result["candidate_version"])
        self.assertEqual(files[0].name, "original_100_P.pak")
        self.assertEqual(files[0].read_bytes(), b"candidate")
        self.assertFalse(self.manager.deployment.enabled_ids())

    def test_no_change_does_not_duplicate_version(self):
        mod = self.mod()
        service = self.engine("""import sys,json,shutil
from pathlib import Path
source=Path(sys.argv[1]); out=Path(sys.argv[sys.argv.index('--outdir')+1])
shutil.copy2(source,out/(source.stem+'_fixed.pak'))
(out/'fix_mod_result.json').write_text(json.dumps([{'converted':0,'padded':0,'risk_level':'fixture'}]))
""")
        service.fix(mod)
        self.assertEqual(len(mod.versions), 1)

    def test_bad_report_and_process_error_preserve_current(self):
        mod = self.mod()
        service = self.engine("import sys;sys.exit(5)")
        with self.assertRaises(RuntimeError):
            service.fix(mod)
        self.assertEqual(len(mod.versions), 1)
        service = self.engine("""import sys
from pathlib import Path
out=Path(sys.argv[sys.argv.index('--outdir')+1]);(out/'fix_mod_result.json').write_text('invalid')
""")
        with self.assertRaises(ValueError):
            service.fix(mod)
        self.assertEqual(len(mod.versions), 1)

    def test_unsupported_companions_and_missing_tool(self):
        mod = self.mod()
        service = self.engine("")
        self.settings.repair_python = str(self.root / "missing.exe")
        with self.assertRaises(FileNotFoundError):
            service.assess(mod)
        mod.versions[0]["files"].append({"name": "extra.utoc", "size": 0, "sha256": "0" * 64})
        with self.assertRaises(ValueError):
            service.assess(mod)
