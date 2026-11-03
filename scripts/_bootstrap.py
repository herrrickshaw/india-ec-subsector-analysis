"""Make ``ec_analysis`` importable when a script is run as ``python3 scripts/x.py``."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def configure_logging() -> None:
    """CLI logging: INFO to stderr, bare message (matches the old ``print(..., file=sys.stderr)``)."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)


def display_path(path: Path) -> str:
    """Path relative to the repo root when inside it (``data/x.json``), else absolute."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)
