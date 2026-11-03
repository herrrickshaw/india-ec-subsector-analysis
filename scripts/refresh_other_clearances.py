#!/usr/bin/env python3
"""Refresh the Forest / Wildlife / CRZ clearance registers from PARIVESH 2.0.

The SAME open, unauthenticated API that serves Environmental Clearances
(majorClearanceType=1, handled by refresh_ec.py) also serves the other three
central green clearances under different type codes:

    majorClearanceType=2  Forest Clearance      (FC)  ~29k proposals, ~34 MB
    majorClearanceType=3  Wildlife Clearance     (WLC) ~5k proposals
    majorClearanceType=4  CRZ Clearance          (CRZ) ~2k proposals

One GET per type returns the whole national register (pageSize/pageNo are
ignored by the server, so the payload is the full set regardless).

The prize field is Forest Clearance's `forest_area` (hectares) -- populated on
92% of proposals -- which is a direct land-QUANTUM measure the EC register
lacks. Forest diversion is a second land-creation channel alongside the
industrial land bank: mining, linear infra and hydro convert forest to
non-forest use here. `clearanceType` gives the FORM (Form-A = fresh diversion;
Form-B/D/E/F = renewal/transfer/re-diversion on already-diverted land), enabling
the forest analogue of the EC fresh-vs-reuse split.

    python3 scripts/refresh_other_clearances.py                 # fetch + rebuild
    python3 scripts/refresh_other_clearances.py --from-dir DIR  # rebuild from
        saved parivesh_type{2,3,4}.json dumps in DIR
    python3 scripts/refresh_other_clearances.py --data-dir DIR  # write elsewhere

The aggregation lives in ec_analysis/other_clearances.py (pure functions; its
docstring carries the grant-rate / forest-area honesty notes).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap
from ec_analysis import other_clearances as oc
from ec_analysis.config import DATA_DIR
from ec_analysis.parivesh import fetch_register, load_dump


def rows_from_dir(directory: Path):
    """Row source reading saved ``parivesh_type{t}.json`` dumps from ``directory``."""
    return lambda t: load_dump(Path(directory) / f"parivesh_type{t}.json")["data"]


def rows_from_api(t: int) -> list:
    return fetch_register(t)["data"]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-dir", dest="d", help="rebuild from saved parivesh_type{2,3,4}.json in DIR")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR, help=f"output directory (default {DATA_DIR})")
    args = ap.parse_args(argv)
    _bootstrap.configure_logging()
    report = oc.build_report(rows_from_dir(args.d) if args.d else rows_from_api)
    for rec in report["clearances"].values():
        print(oc.summary_line(rec))
    path = oc.write_report(report, args.data_dir)
    print(f"wrote {_bootstrap.display_path(path)}")


if __name__ == "__main__":
    main()
