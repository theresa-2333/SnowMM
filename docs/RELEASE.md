# SnowMM v1.0.0 发布

## 交付文件

`dist/release/` 中生成以下文件：

- `SnowMM-1.0.0-windows-x64.zip`：完整解压后运行 `SnowMM/SnowMM.exe`，保留 `_internal`。
- `SnowMM-1.0.0-source.zip`：源码、旧版归档、测试、工具、文档和全部内置资源。
- `SnowMM-1.0.0-assets.zip`：独立角色、属性、图标与来源清单资源包。
- `snowmm-1.0.0-py3-none-any.whl` / `.tar.gz`：Python 包与 sdist（如果已构建）。
- `SHA256SUMS.txt`：校验值。
- `RELEASE_NOTES.md`：供 GitHub Release 使用的双语说明。

## 本地构建

```powershell
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -t .
python tests/smoke_ui.py
python tests/regression_ui.py
python -m ruff check .
pwsh -NoProfile -File tools/build_exe.ps1
python tools/verify_release.py
python -m build
python tools/package_release.py
```

`verify_release.py` 设置独立的 `SNOWMM_HOME` 与 Qt 离屏平台，再运行打包后的 EXE 自检。
验证 54 张图片、全部角色英文名、应用图标和页面切换；报告写入 `dist/release-self-test.json`。
测试不操作真实用户数据库和游戏模组。Windows 包为 x64，未进行数字签名。

## GitHub 发布步骤

先检查全部修改与发布包，再将更新分支推送至
`https://github.com/theresa-2333/Snowbreak_Mod_Manager`，通过 PR 审阅合入默认分支。
GitHub Release 以 `v1.0.0` 为标签，标题使用 `SnowMM v1.0.0 — Major Update`。
发布说明使用 `dist/release/RELEASE_NOTES.md`，上传全部 ZIP、wheel、sdist 和校验文件。
可先创建 Draft Release，确认后再公开发布。

如未登录，使用 GitHub 官方 CLI 的 `gh auth login` 或 Git Credential Manager 的交互式登录。
不要把访问令牌写入源码、发布包或聊天。

## 升级说明

升级只替换应用目录，保留 `%APPDATA%/SnowMM/`。建议先使用设置页备份数据库。
语言切换不会更改已有中文角色目录。旧版源码位于 `snow_mod_manager/`。
压缩包导入继续暂停；真实游戏挂载行为仍需实际游戏环境验证。
