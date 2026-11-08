"""Subprocess adapter: assessments are observations, repaired files are candidates."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from .storage import atomic_json, digest, inside, linked


class RepairService:
    def __init__(self, settings):
        self.settings = settings

    @property
    def tool(self):
        return Path(self.settings.repair_tool)

    def describe(self):
        names = ("fix_mod.py", "assess_mod.py", "repak.exe", "skeleton_db.json", "roles_body.json", "redirects.json")
        return {
            "path": str(self.tool),
            "source": "https://www.nexusmods.com/snowbreakcontainmentzone/mods/1050",
            "target_game": "数据快照适配版本待确认，不代表已匹配当前游戏",
            "files": [
                {"name": n, "sha256": digest(self.tool / n) if (self.tool / n).is_file() else "缺失"} for n in names
            ],
        }

    def _run(self, script, args, cwd):
        if not self.settings.repair_tool or not self.settings.repair_python:
            raise FileNotFoundError("可选修复工具尚未配置，请自行获取工具并在增强设置指定路径")
        python = Path(self.settings.repair_python)
        if not python.is_file() or not (self.tool / script).is_file():
            raise FileNotFoundError("修复工具或独立 Python 缺失，请在增强设置检查路径")
        environment = dict(
            os.environ,
            PYTHONIOENCODING="utf-8",
            PYTHONNOUSERSITE="1",
            PYTHONDONTWRITEBYTECODE="1",
            REPAK=str((self.tool / "repak.exe").absolute()),
        )
        environment.pop("PYTHONPATH", None)
        result = subprocess.run(
            [str(python), str(self.tool / script), *map(str, args)],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode:
            raise RuntimeError(f"工具失败（{result.returncode}）：{result.stderr[-2500:]}\n{result.stdout[-2500:]}")
        return result.stdout

    @staticmethod
    def _inputs(mod):
        files = mod.files()
        if any(p.suffix.lower() in {".utoc", ".ucas", ".sig"} for p in files):
            raise ValueError("此工具仅支持独立 PAK；IoStore/UTOC/UCAS/签名配套包不执行转换")
        paks = [p for p in files if p.suffix.lower() == ".pak"]
        if not paks:
            raise ValueError("当前版本没有 PAK")
        for p, info in zip(files, mod.version()["files"], strict=True):
            if not p.is_file() or linked(p) or digest(p) != info["sha256"]:
                raise ValueError("源文件校验失败，停止处理")
        return paks

    def assess(self, mod):
        reports = []
        # A temporary working directory avoids changing the shared engine directory.
        with tempfile.TemporaryDirectory(prefix="snowmm-assess-") as temp:
            for pak in self._inputs(mod):
                output = self._run("assess_mod.py", [pak, "--json"], temp)
                try:
                    reports.append(json.loads(output))
                except ValueError as error:
                    raise ValueError("评估报告不是有效 JSON；未改变模组") from error
        return {
            "version": mod.current_version,
            "engine": self.describe(),
            "reports": reports,
            "in_game_verified": False,
        }

    def fix(self, mod):
        sources = self._inputs(mod)
        if not (self.tool / "repak.exe").is_file():
            raise FileNotFoundError("随附 repak.exe 缺失；不自动下载或改用未知打包器")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        version_id = f"v{len(mod.versions) + 1:03d}_修复候选_{stamp}"
        with tempfile.TemporaryDirectory(prefix="snowmm-fix-") as temporary:
            work = Path(temporary)
            logs, reports, outputs = [], [], []
            for index, pak in enumerate(sources):
                out = work / str(index)
                out.mkdir()
                logs.append(self._run("fix_mod.py", [pak, "--outdir", out, "--json"], work))
                report_file = out / "fix_mod_result.json"
                if not report_file.is_file():
                    raise ValueError("修复未生成汇总报告")
                result = json.loads(report_file.read_text(encoding="utf-8-sig"))
                if not isinstance(result, list) or len(result) != 1:
                    raise ValueError("修复报告结构不符合预期")
                report = result[0]
                if report.get("err") or report.get("risk_level") == "ERROR":
                    raise ValueError(f"修复失败：{report.get('err', 'ERROR')}")
                expected = out / (pak.stem + "_fixed.pak")
                if not expected.is_file() or linked(expected) or expected.stat().st_size == 0:
                    raise ValueError("修复输出缺失或无效")
                # Re-parse the candidate rather than accepting only an exit code.
                assessment = json.loads(self._run("assess_mod.py", [expected, "--json"], work))
                reports.append({"repair": report, "assessment": assessment})
                outputs.append((pak.name, expected))
            report = {
                "source_version": mod.current_version,
                "created": stamp,
                "engine": self.describe(),
                "items": reports,
                "logs": logs,
                "in_game_verified": False,
            }
            if all(not r["repair"].get("converted") and not r["repair"].get("padded") for r in reports):
                report["message"] = "未发生转换，不重复建立相同版本"
                folder = Path(mod.folder) / "报告"
                folder.mkdir(exist_ok=True)
                atomic_json(folder / f"{stamp}_{uuid.uuid4().hex[:6]}.json", report)
                return report
            destination = inside(Path(mod.folder), Path(mod.folder) / "版本" / version_id)
            destination.mkdir()
            old_history = mod.repair_history[:]
            try:
                information = []
                for name, output in outputs:
                    target = destination / name  # Restore the original priority-bearing basename.
                    shutil.copy2(output, target)
                    information.append({"name": name, "size": target.stat().st_size, "sha256": digest(target)})
                # SIG files authenticate the original bytes; they cannot be reused after conversion.
                if any(p.suffix.lower() == ".sig" for p in mod.files()):
                    raise ValueError("含签名配套文件的 PAK 不自动生成修复版本")
                mod.versions.append(
                    {
                        "id": version_id,
                        "label": "修复候选（未实测）",
                        "files": information,
                        "game_versions": mod.game_versions,
                        "tested": "未实测",
                    }
                )
                report["candidate_version"] = version_id
                mod.repair_history.append(report)
                folder = Path(mod.folder) / "报告"
                folder.mkdir(exist_ok=True)
                atomic_json(folder / f"{version_id}.json", report)
                mod.save()  # Does not select or deploy the new revision.
            except BaseException:
                mod.versions = [v for v in mod.versions if v["id"] != version_id]
                mod.repair_history = old_history
                shutil.rmtree(destination)
                raise
        return report
