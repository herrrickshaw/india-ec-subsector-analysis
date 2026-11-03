#!/usr/bin/env python3
"""Refresh the Environmental Clearance state x sub-sector matrix from PARIVESH 2.0.

PARIVESH 2.0 exposes a fully open, unauthenticated JSON API — no key, no
CAPTCHA, no pagination — that returns the entire national EC proposal register
in a single GET. One call replaces a scraping campaign.

    Endpoint: https://parivesh.nic.in/parivesh_api/trackYourProposal/advanceSearchData
    Params:   majorClearanceType=1  (1 = Environmental Clearance)
              state=  proposalStatus=  pageNo=0  pageSize=200000

Each proposal carries: state, an EIA-schedule Activity code in other_property
(this is the SUB-SECTOR — e.g. "1(a) Mining of minerals", "5(f) Synthetic
organic chemicals"), proposalStatus, category (A/B1/B2), issuing authority.

Output: data/ec_state_subsector_matrix.json (state x activity x status counts),
data/ec_subsector_analysis.json (per-sub-sector grant rate + state leaders),
data/ec_state_subsector.csv (flat pivot). Build docs with build_page.py.

    python3 scripts/refresh_ec.py                  # fetch + rebuild
    python3 scripts/refresh_ec.py --from FILE      # rebuild from a saved dump
    python3 scripts/refresh_ec.py --data-dir DIR   # write outputs elsewhere

The aggregation itself lives in ec_analysis/ec.py (pure functions; see its
docstring for the status-bucket and grant-rate method).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap
from ec_analysis import ec
from ec_analysis.config import DATA_DIR, EC_TYPE
from ec_analysis.parivesh import fetch_register, load_dump


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="src", help="rebuild from a saved JSON dump instead of fetching")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR, help=f"output directory (default {DATA_DIR})")
    args = ap.parse_args(argv)
    _bootstrap.configure_logging()
    envelope = load_dump(args.src) if args.src else fetch_register(EC_TYPE)
    matrix_doc, analysis_doc = ec.build(envelope, data_dir=args.data_dir)
    print(ec.summary_line(matrix_doc, analysis_doc))


if __name__ == "__main__":
    main()
