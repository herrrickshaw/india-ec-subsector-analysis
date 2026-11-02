"""Forest / Wildlife / CRZ clearances (majorClearanceType 2/3/4) pipeline.

    rows -> summarise_register(rows, kind, label) -> dict   (one per type)
         -> build_report(get_rows) -> full document -> write_report()

Honesty notes carried into the output:
 - Grant rate = granted / (granted + in_process); 'dead' (rejected/withdrawn/
   returned) and 'delisted' (PARIVESH auto-cleanup) are excluded from the
   denominator, matching the EC methodology.
 - FC 'granted' = "Final Diversion Order Issued" or "Stage-II Accorded" (final
   approval). Stage-I (in-principle) is NOT counted as granted.
 - The forest_area PIPELINE total mixes all statuses (incl. delisted) and is
   skewed by a single ~74,000-ha outlier; the GRANTED forest-area total is the
   trustworthy "forest actually diverted" figure and is reported separately.
"""
from __future__ import annotations

import collections
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Callable, Iterable

from ec_analysis.config import (
    AGENCY_LABEL_MAX_CHARS,
    DATA_DIR,
    FOREST_TOP_AGENCIES,
    FOREST_TOP_STATES,
    FORM_LABEL_MAX_CHARS,
    HA_TO_ACRE,
    OTHER_DEAD_KEYWORDS,
    OTHER_LIVE_BUCKETS,
    OTHER_OUTPUT_FILE,
    OTHER_TOP_STATES,
    OTHER_TYPES,
    UNSPECIFIED_STATE,
)

log = logging.getLogger(__name__)

Row = dict[str, Any]
RowSource = Callable[[int], list]  # clearance_type -> proposal rows

REPORT_HEADER = {
    "source": ("PARIVESH 2.0 advanceSearchData, majorClearanceType 2=Forest 3=Wildlife 4=CRZ "
               "(full national register)"),
    "note": ("Companion to the Environmental Clearance analysis (majorClearanceType=1). Same open "
             "API, same pipeline-snapshot semantics -- proposals span 2022 to the fetch date, "
             "status is as-of-fetch."),
    "method": ("Grant rate = granted / (granted + in_process); 'dead' and 'delisted' excluded from "
               "the denominator. FC 'granted' = Final Diversion Order Issued or Stage-II Accorded."),
}
FOREST_AREA_CAVEAT = ("pipeline_total mixes all statuses incl. delisted and is skewed by a single "
                      "~74,000-ha outlier; 'granted' is the trustworthy forest-actually-diverted figure")
FORM_TYPE_READING = ("Form-A is a FRESH diversion of forest land; Form-B/D/E/F are renewals, transfers "
                     "and re-diversions on already-diverted land -- the forest analogue of the EC "
                     "fresh-vs-reuse split.")


def parse_number(x: Any) -> float | None:
    """'1,234.5' -> 1234.5; anything non-numeric -> None."""
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def _is_dead(s: str) -> bool:
    return any(x in s for x in OTHER_DEAD_KEYWORDS)


def bucket_status(status: str | None, kind: str) -> str:
    """Per-type status bucketing -- each clearance has its own status vocabulary."""
    s = (status or "").lower()
    if "delist" in s:
        return "delisted"
    if s == "removed":
        return "dead"
    if kind == "FC":
        if "final diversion order issued" in s or "stage-ii accorded" in s:
            return "granted"
        if _is_dead(s):
            return "dead"
        return "in_process"   # incl. Stage-I in-principle, all "Pending at ..." and EDS states
    if kind == "WLC":
        if ("recommend" in s and "not" not in s) or "dispos" in s:
            return "granted"   # NBWL/SBWL recommendation is the approval instrument
        if _is_dead(s):
            return "dead"
        return "in_process"
    # CRZ
    if "grant" in s:
        return "granted"
    if _is_dead(s):
        return "dead"
    return "in_process"


def normalise_state(row: Row) -> str:
    """Upper-cased, stripped state name; missing -> UNSPECIFIED (blank strings are kept blank)."""
    return (row.get("state") or UNSPECIFIED_STATE).strip().upper()


def _forest_extras(rows: Iterable[Row], buckets: Iterable[str]) -> dict[str, Any]:
    """FC-only: forest_area totals (ha/acres), by-state, by form type, top user agencies."""
    forest_state: dict[str, dict[str, float]] = collections.defaultdict(lambda: collections.defaultdict(float))
    forms: collections.Counter = collections.Counter()
    agencies: collections.Counter = collections.Counter()
    fa_total = fa_granted = 0.0
    for row, b in zip(rows, buckets):
        st = normalise_state(row)
        area = parse_number(row.get("forest_area")) or 0.0
        if area > 0:
            fa_total += area
            forest_state[st]["all"] += area
            if b == "granted":
                fa_granted += area
                forest_state[st]["granted"] += area
        forms[(row.get("clearanceType") or "?").strip()[:FORM_LABEL_MAX_CHARS]] += 1
        agencies[(row.get("nameOfUserAgency") or "?").strip()[:AGENCY_LABEL_MAX_CHARS]] += 1

    def forms_starting(*prefixes: str) -> int:
        return sum(n for f, n in forms.items() if f.startswith(prefixes))

    return {
        "forest_area_ha": {
            "pipeline_total": round(fa_total), "granted": round(fa_granted),
            "acres_pipeline": round(fa_total * HA_TO_ACRE), "acres_granted": round(fa_granted * HA_TO_ACRE),
            "caveat": FOREST_AREA_CAVEAT},
        "forest_area_by_state": [
            {"state": s.title(), "pipeline_ha": round(a["all"]), "granted_ha": round(a["granted"]),
             "granted_acres": round(a["granted"] * HA_TO_ACRE)}
            for s, a in sorted(forest_state.items(), key=lambda kv: -kv[1]["all"])[:FOREST_TOP_STATES]],
        "by_form_type": {
            "fresh_diversion_FormA": forms_starting("Form-A"),
            "re_diversion_FormE": forms_starting("Form-E"),
            "renewal_FormBD": forms_starting("Form-B", "Form-D"),
            "transfer_FormF": forms_starting("Form-F"),
            "reading": FORM_TYPE_READING},
        "top_user_agencies": [{"agency": a, "proposals": n}
                              for a, n in agencies.most_common(FOREST_TOP_AGENCIES + 1)
                              if a != "?"][:FOREST_TOP_AGENCIES],
    }


def summarise_register(rows: list, kind: str, label: str) -> dict[str, Any]:
    """Funnel, grant rate and top states for one clearance type; FC adds forest-area extras."""
    buckets = [bucket_status(r.get("proposalStatus"), kind) for r in rows]
    funnel: collections.Counter = collections.Counter(buckets)
    by_state: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for row, b in zip(rows, buckets):
        by_state[normalise_state(row)][b] += 1
    live = sum(funnel[k] for k in OTHER_LIVE_BUCKETS)
    rec = {
        "code": kind, "label": label, "total": len(rows), "n_states": len(by_state),
        "funnel": dict(funnel),
        "grant_rate_pct_of_decided": round(funnel["granted"] / live * 100, 1) if live else None,
        "top_states": [{"state": s.title(), "total": sum(c.values()), "granted": c["granted"],
                        "pending": c["in_process"]}
                       for s, c in sorted(by_state.items(), key=lambda kv: -sum(kv[1].values()))[:OTHER_TOP_STATES]],
    }
    if kind == "FC":
        rec.update(_forest_extras(rows, buckets))
    return rec


def summary_line(rec: dict[str, Any]) -> str:
    """One-line human summary for one clearance type (printed by the CLI)."""
    line = (f"{rec['code']}: {rec['total']:,} proposals | grant% {rec['grant_rate_pct_of_decided']} | "
            f"{rec['n_states']} states")
    if rec["code"] == "FC":
        fa = rec["forest_area_ha"]
        line += f" | forest granted {fa['granted']:,} ha ({fa['acres_granted']:,} ac)"
    return line


def build_report(get_rows: RowSource, built: str | None = None) -> dict[str, Any]:
    """Assemble the ``parivesh_other_clearances.json`` document from a row source."""
    out: dict[str, Any] = {"built": built or datetime.date.today().isoformat(), **REPORT_HEADER, "clearances": {}}
    for clearance_type, (kind, label) in OTHER_TYPES.items():
        out["clearances"][kind] = summarise_register(get_rows(clearance_type), kind, label)
    return out


def write_report(report: dict[str, Any], data_dir: Path = DATA_DIR) -> Path:
    """Write the report JSON into ``data_dir``; returns the path written."""
    path = Path(data_dir) / OTHER_OUTPUT_FILE
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    return path
