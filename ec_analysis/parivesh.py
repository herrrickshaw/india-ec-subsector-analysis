"""Network edge: fetch a PARIVESH 2.0 register, or load a saved dump."""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Callable

from ec_analysis.config import API_URL, CURL_TIMEOUT_S, SUBPROCESS_TIMEOUT_S

log = logging.getLogger(__name__)

Fetcher = Callable[[str], str]


def curl_get(url: str) -> str:
    """GET ``url`` with the system curl and return the response body."""
    out = subprocess.run(
        ["curl", "-s", "-m", str(CURL_TIMEOUT_S), url],
        capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_S, check=False,
    )
    return out.stdout


def fetch_register(clearance_type: int, fetcher: Fetcher = curl_get) -> dict[str, Any]:
    """Fetch the full national register for ``majorClearanceType=clearance_type``.

    Returns the decoded JSON envelope (``{"data": [...proposals...]}``).
    ``fetcher`` is injectable so tests never touch the network.
    """
    log.info("fetching PARIVESH majorClearanceType=%s ...", clearance_type)
    return json.loads(fetcher(API_URL.format(clearance_type=clearance_type)))


def load_dump(path: str | Path) -> dict[str, Any]:
    """Load a saved API envelope from disk (same shape as :func:`fetch_register`)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
