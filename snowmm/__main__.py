"""Entry point used by ``python -m snowmm`` and the packaged executable."""

from __future__ import annotations

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
