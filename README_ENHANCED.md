# SnowMM 增强功能贡献版

基于 SnowMM v1.1.0，提交 `bd7371bf8d95545d668c62cb005ac495bbc0121a`。增强版本标识1.1.0-enhanced.3。此文件集用于向上游提交功能补充，不代表上游已采纳或发布。

## 功能

- 中文多级分类、侧栏大分类和图鉴风格小分类卡片；保留角色图鉴、皮肤、画廊和搜索。
- 每个模组独立保存mod.json、版本、原始包、说明和预览；索引可重建。
- 符号链接/复制部署、配套文件、归属清单、互斥组、启用方案、失败回滚和游戏运行待办。
- 桌面框选截图、全局热键、确认归属、剪贴板预览。
- 用户发起的UAC重启；修复Windows扩展盘符/UNC链接校验误报。
- 外部1050修复工具适配器，生成独立候选，不覆盖原件；此贡献不附带该工具及运行时。

## 来源与权利

上游：https://github.com/theresa-2333/SnowMM
修复工具：https://www.nexusmods.com/snowbreakcontainmentzone/mods/1050
参考功能：https://github.com/eggao/SnowBreak-MOD-manager 、Nexus 983/1006及d3dx-Sr；没有复制这些管理器的程序和素材。保留原THIRD_PARTY_NOTICES.md署名。

上游当前没有根LICENSE声明，此贡献没有替上游代码或游戏素材授予新许可。先按fork/PR方式请求维护者审阅；正式发布完整源码镜像、素材或可执行包前由维护者确认相应许可。这个文件集不含第三方修复代码、规则表、repak、Python运行时、游戏模组或字体。

## 公开依赖与选择原因

| 依赖 | 本次验证版本与来源 | 用途 |
| --- | --- | --- |
| Python | [3.11 x64](https://www.python.org/downloads/windows/) | 本次开发与测试环境，不上传本机解释器 |
| PySide6 | [6.12.0](https://pypi.org/project/PySide6/6.12.0/) | 沿用Qt图鉴界面和桌面截图 |
| py7zr | [1.1.4](https://pypi.org/project/py7zr/1.1.4/) | 沿用7z安全导入 |
| rarfile | [4.5](https://pypi.org/project/rarfile/4.5/) | 沿用RAR识别；解压后端由用户另装 |
| psutil | [7.2.2](https://pypi.org/project/psutil/7.2.2/) | 判断游戏进程，避免运行时直接改变部署 |
| PyInstaller | [6.22.3](https://pypi.org/project/pyinstaller/6.22.3/) | 开发时打包Windows便携目录 |
| Ruff / Pillow | [0.17.4](https://pypi.org/project/ruff/0.17.4/) / [13.0.0](https://pypi.org/project/pillow/13.0.0/) | 代码检查、上游图像开发验证 |

上述均声明为公开安装依赖，未附带作者的虚拟环境。传递依赖由pip解析；这里不是覆盖全部传递依赖的完整锁文件。

## 开发运行

在上游源码目录叠加本文件集，建议使用Python 3.11 x64和独立虚拟环境：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-enhanced-dev.txt
.\.venv\Scripts\python.exe enhanced_main.py
```

venv隔离开发依赖；pip从公开包仓库安装明确列出的依赖；enhanced_main.py为新增入口，main.py仍为原入口。没有依赖作者电脑的虚拟环境或绝对路径。

首次打开进入增强设置：资源库建议为当前用户目录下SnowMM/Library；选择实际Game.exe后填入其对应的Paks/~SnowMM建议目录，再检查并保存。游戏、服务端、工具路径初始为空，不会自动扫描其他磁盘或读取原版AppData。

## 可选修复工具

不使用修复功能时无需安装额外工具。需要时自行从1050来源获取工具，在增强设置指定其目录和适配的Python解释器；缺少工具只提示不可用，不影响分类、部署和截图。服务端启动同样需用户自行选择EXE，不附带服务端或账号数据。

## 验证与构建

```powershell
New-Item -ItemType Directory -Path .test-temp -Force
$env:TEMP = "$PWD/.test-temp"
$env:TMP = $env:TEMP
$env:SNOWMM_HOME = "$PWD/.upstream-test"
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
.\.venv\Scripts\python.exe tests/enhanced_ui.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe enhanced_main.py --self-test self-test.json
powershell -NoProfile -File tools/build_enhanced.ps1
```

临时目录和SNOWMM_HOME将上游迁移测试隔离，避免接触真实配置；unittest运行回归，enhanced_ui执行离屏界面验证，ruff检查Python代码，self-test仅使用一次性模组。缺少Windows真实链接权限会报告跳过，未配置外部修复工具会报告可选项未配置。构建脚本仅封装程序和依赖，不复制data、修复工具或本地环境。

构建输出为dist/SnowMMEnhanced，完整目录才是便携版。正式公开发布前应由维护者确认上游及依赖许可，并在真实Windows环境完成管理员链接、游戏加载、多显示器和修复候选验证。

当前增强工作台为中文，保留上游原界面的中英切换；尚未全面英文化。本次准备包只提供源码贡献，不附带公开发布的EXE。
