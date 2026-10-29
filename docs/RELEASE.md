# SnowMM v1.1.0 发布

发布日期：2026-10-29。发行仓库：[theresa-2333/SnowMM](https://github.com/theresa-2333/SnowMM)。

## 发布文件

- `SnowMM-1.1.0-windows-x64.zip`：完整解压后运行 `SnowMM/SnowMM.exe`，保留 `_internal`。
- `SnowMM-1.1.0-source.zip`：源码、旧版归档、测试、工具、文档和全部资源。
- `SnowMM-1.1.0-assets.zip`：角色、属性、图标、时装目录及来源清单。
- `snowmm-1.1.0-py3-none-any.whl` / `.tar.gz`：Python 包与源码分发。
- `SHA256SUMS.txt`：发布文件的 SHA-256 校验。

构建输出隔离在 `dist/release/1.1.0/`，不会混入旧版本发行包。

## 本地验证

```powershell
python -m unittest discover -s tests -t .
python tests/smoke_ui.py
python tests/regression_ui.py
python tests/update_ui.py
python tests/gallery_ui.py
python -m ruff check .
pwsh -NoProfile -File tools/build_exe.ps1
python tools/verify_release.py
python -m build
python tools/package_release.py
python tools/audit_release.py
```

Python 包应从干净源码目录构建，避免旧 `build/lib` 留下中文资源路径。
冻结应用自检使用独立 `SNOWMM_HOME`，验证立绘、图标、自动旧目录兼容、页面内画廊、
ZIP／7z 实际导入与 RAR 库加载，不修改真实游戏模组。Windows 包为 x64，未签名。

## GitHub

将更新推送至更新分支，经 PR 合入仓库默认分支；以通过验证的提交创建 `v1.1.0` 标签。
上传发行包、发布说明和校验文件，校验上传后的大小与摘要，再公开 Release。
不要把用户数据库、模组文件或凭据加入 Git 或发行包。

## 升级

完整替换应用目录，保留 `%APPDATA%/SnowMM/`。启动及选择／扫描目录时自动修复旧布局，
转换前生成数据库快照，失败可重试；详见 [更新说明](UPDATE_1.1.md)。
画廊在当前页面切换，提供返回按钮及快捷开关。Nexus 下载未开发；真实游戏挂载尚未实测。
