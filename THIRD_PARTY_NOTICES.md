# Third-party notices

## Snowbreak artwork and names

Snowbreak: Containment Zone, its characters, artwork, names and trademarks belong
to Amazing Seasun Games and their respective rights holders. SnowMM is an
unofficial fan utility and is not affiliated with or endorsed by the game publisher.
Bundling these assets does not change their ownership or grant an additional license.

Portrait reference pages:

- https://www.gamekee.com/snow/second/61949
- https://wiki.biligame.com/sonw/芙提雅·炬芯

Individual source pages, image URLs, dimensions and SHA-256 hashes are bundled in
`snowmm/assets/catalog/artwork.json`. The damage-type symbols are retained from the
existing project resources. English names were checked against:

- https://snowbreak.fandom.com/wiki/Characters
- https://gacha-data.com/snowbreak/characters/

The application emblem was redrawn from the reference provided by the project owner
with the built-in imagegen tool. See `docs/ICON_DESIGN.md` for the generation prompt.

## Qt / PySide6 / Shiboken

The Windows distribution includes unmodified PySide6, Shiboken and Qt runtime
components. Qt for Python is available under LGPLv3/GPLv3 and commercial terms;
individual Qt components may carry additional notices. Upstream licensing and source:

- https://doc.qt.io/qtforpython-6/licenses.html
- https://code.qt.io/cgit/pyside/pyside-setup.git/
- https://code.qt.io/cgit/qt/

Qt libraries remain separate files in the portable application's `_internal` directory.
The release includes upstream license texts when supplied by the installed packages.

## Python and packaging

The portable build embeds Python, distributed under the Python Software Foundation
License. https://docs.python.org/3/license.html

PyInstaller is used to produce the executable. Its bootloader exception allows
redistribution of bundled applications under their own terms.
https://pyinstaller.org/en/stable/license.html

JASM is credited as interface inspiration; no JASM application code is bundled.
https://github.com/Kiyanami/JASM

## Skin names and archive libraries

Skin names and their English labels are transcribed from BWIKI's outfit index;
the source URL and retrieval date are recorded in `assets/catalog/skins.json`.
No outfit images or descriptive text are copied.
https://wiki.biligame.com/sonw/时装一览

Archive support uses py7zr (LGPL-2.1-or-later) and rarfile (ISC), together with
their dependencies. RAR decompressor executables are detected on the user's
machine; no WinRAR / UnRAR / 7-Zip executable is redistributed in this repository.
https://github.com/miurahr/py7zr
https://github.com/markokr/rarfile
