"""SnowMM - a modern mod manager for Snowbreak: Containment Zone.

The package is intentionally split into a Qt-free ``core`` layer (data model,
storage, catalog and filesystem operations) and a ``ui`` layer built on
PySide6.  Keeping the core free of Qt makes it unit-testable and reusable for
future front-ends.
"""

__all__ = ["APP_NAME", "APP_TITLE", "__version__"]

__version__ = "1.1.0"
APP_NAME = "SnowMM"
APP_TITLE = "SnowMM - Snowbreak Mod Manager"
