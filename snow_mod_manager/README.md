# snow_mod_manager · 存档（0.2.x）

这里是**重构前的旧实现**，只作对照与回退用途，不参与 1.0 的构建与测试：

| 文件 | 说明 |
| --- | --- |
| `mod_manager_v0.2.2.py` | 最后一个单文件版本（PyQt5，约 1300 行），对应 0.2.2 |
| `translations.py` | 0.2.2 的中英文文案 |
| `img/cbjq.ico`、`img/check.svg` | 0.2.2 用到的图标资源 |
| `history/` | 更早的 0.2 / 0.2.1 脚本，以及当时的界面截图 |

运行方式（需要 PyQt5，且必须在本目录内运行，因为它按相对路径导入 `translations`）：

```bash
pip install PyQt5
cd snow_mod_manager
python mod_manager_v0.2.2.py
```

旧版把数据放在 `~/.snowbreak_mod_manager/`（`projects.json`、`config.json`、`images/`），
新版 SnowMM 首次启动会自动迁移这份数据，详见根目录的 `README.md`。

新版代码在 `snowmm/`，与这里完全独立。
