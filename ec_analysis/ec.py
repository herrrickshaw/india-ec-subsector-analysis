"""Environmental Clearance (majorClearanceType=1): state x sub-sector pipeline.

Stages, each a pure function over plain dicts/lists so they are testable on a
handful of synthetic rows:

    rows -> aggregate() -> EcAggregate -> matrix_document() / subsector_analysis()
                                        -> csv_rows() -> write_outputs()

Status buckets: 'delisted' is PARIVESH's auto-cleanup of inactive applications
(~22% of the register) -- excluded from grant-rate denominators, kept in totals
so the exclusion is visible. Grant rate = granted / (granted + tor_granted +
in_process); dead = rejected/withdrawn/closed/lapsed/returned.
"""
from __future__ import annotations

import collections
import csv
import datetime
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from ec_analysis.config import (
    DATA_DIR,
    EC_ANALYSIS_FILE,
    EC_CSV_FILE,
    EC_DEAD_KEYWORDS,
    EC_LABEL_MAX_CHARS,
    EC_LIVE_BUCKETS,
    EC_MATRIX_FILE,
    EC_MIN_SUBSECTOR_TOTAL,
    EC_TOP_STATES,
    UNCLASSIFIED,
    UNSPECIFIED_STATE,
)

log = logging.getLogger(__name__)

ACTIVITY_RE = re.compile(r"^\s*(\d+\([a-z]+\))\s*(.*)")
SOURCE_NOTE = "PARIVESH 2.0 advanceSearchData?majorClearanceType=1 (Environmental Clearance), full register"

Row = dict[str, Any]
Cell = tuple[str, str, str]  # (state, activity_code, status_bucket)


@dataclass
class EcAggregate:
    """Counts per (state, activity, bucket) plus activity labels and the unparseable count."""

    matrix: collections.Counter = field(default_factory=collections.Counter)
    activity_labels: dict[str, str] = field(default_factory=dict)
    unclassified: int = 0
    n_rows: int = 0


def bucket_status(status: str | None) -> str:
    """Map a free-text proposalStatus to granted/tor_granted/in_process/dead/delisted."""
    s = (status or "").lower()
    if "tor" in s and "grant" in s:
        return "tor_granted"
    if "grant" in s:
        return "granted"
    if "delist" in s:
        return "delisted"
    if any(x in s for x in EC_DEAD_KEYWORDS):
        return "dead"
    return "in_process"


def parse_properties(row: Row) -> dict[str, Any]:
    """Decode the ``other_property`` JSON list of {label, value} into a dict; {} if malformed."""
    raw = row.get("other_property") or "[]"
    try:
        return {p["label"]: p["value"] for p in json.loads(raw)}
    except (ValueError, TypeError, KeyError) as exc:
        log.debug("unparseable other_property %r: %s", raw[:80] if isinstance(raw, str) else raw, exc)
        return {}


def parse_activity(activity: str) -> tuple[str, str | None]:
    """Split "1(a) Mining of minerals" into ("1(a)", "Mining of minerals").

    Returns ``(code, None)`` when no EIA-schedule code is present: the first
    whitespace token if any, else :data:`UNCLASSIFIED`.
    """
    m = ACTIVITY_RE.match(activity)
    if m:
        return m.group(1), m.group(2).strip()[:EC_LABEL_MAX_CHARS]
    return (activity.split()[0] if activity.strip() else UNCLASSIFIED), None


def normalise_state(row: Row) -> str:
    """Upper-cased, stripped state name; blank -> UNSPECIFIED."""
    return str(row.get("state") or "").strip().upper() or UNSPECIFIED_STATE


def aggregate(rows: Iterable[Row]) -> EcAggregate:
    """Count proposals per (state, activity code, status bucket)."""
    agg = EcAggregate()
    for row in rows:
        agg.n_rows += 1
        activity = str(parse_properties(row).get("Activity") or "")
        code, label = parse_activity(activity)
        if label is not None:
            agg.activity_labels[code] = label
        else:
            agg.unclassified += 1
        agg.matrix[(normalise_state(row), code, bucket_status(row.get("proposalStatus")))] += 1
    return agg


def matrix_document(agg: EcAggregate, built: str) -> dict[str, Any]:
    """The ``ec_state_subsector_matrix.json`` document (cells sorted by key)."""
    return {
        "built": built,
        "source": SOURCE_NOTE,
        "total_proposals": agg.n_rows,
        "n_states": len({k[0] for k in agg.matrix}),
        "n_subsectors": len(agg.activity_labels),
        "unclassified_activity": agg.unclassified,
        "activity_labels": agg.activity_labels,
        "matrix": [{"state": s, "activity": c, "status": b, "count": n}
                   for (s, c, b), n in sorted(agg.matrix.items())],
    }


def _is_analysable(code: str, total: int) -> bool:
    return total >= EC_MIN_SUBSECTOR_TOTAL and code != UNCLASSIFIED and ")" in code


def subsector_analysis(agg: EcAggregate, built: str) -> dict[str, Any]:
    """The ``ec_subsector_analysis.json`` document: grant rate + state leaders per sub-sector."""
    subsec: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    sub_state: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    state_tot: collections.Counter = collections.Counter()
    for (s, c, b), n in agg.matrix.items():
        subsec[c][b] += n
        state_tot[s] += n
        if b == "granted":
            sub_state[c][s] += n
    analysis = []
    for code, st in sorted(subsec.items(), key=lambda kv: -sum(kv[1].values())):
        tot = sum(st.values())
        if not _is_analysable(code, tot):
            continue
        live = sum(v for k, v in st.items() if k in EC_LIVE_BUCKETS)
        gtot = sum(sub_state[code].values()) or 1
        analysis.append({
            "activity": code, "label": agg.activity_labels.get(code, "?"), "total": tot,
            "granted": st["granted"], "tor_granted": st["tor_granted"],
            "in_process": st["in_process"], "dead": st["dead"], "delisted": st["delisted"],
            "grant_rate_pct": round(st["granted"] / live * 100, 1) if live else None,
            "top_states": [{"state": s.title(), "granted": n, "share_pct": round(n / gtot * 100, 1)}
                           for s, n in sub_state[code].most_common(EC_TOP_STATES)],
        })
    return {
        "built": built,
        "n_subsectors": len(analysis),
        "subsector_analysis": analysis,
        "state_totals": [{"state": s.title(), "total": n} for s, n in state_tot.most_common()],
    }


def csv_rows(matrix_doc: dict[str, Any]) -> Iterator[list[Any]]:
    """Flat ``state, activity_code, activity_label, status, count`` rows (header first)."""
    labels = matrix_doc["activity_labels"]
    yield ["state", "activity_code", "activity_label", "status", "count"]
    for c in matrix_doc["matrix"]:
        yield [c["state"], c["activity"], labels.get(c["activity"], ""), c["status"], c["count"]]


def write_outputs(matrix_doc: dict[str, Any], analysis_doc: dict[str, Any],
                  data_dir: Path = DATA_DIR) -> None:
    """Write the three EC data files into ``data_dir``."""
    data_dir = Path(data_dir)
    with open(data_dir / EC_MATRIX_FILE, "w", encoding="utf-8") as f:
        json.dump(matrix_doc, f, indent=0)
    with open(data_dir / EC_ANALYSIS_FILE, "w", encoding="utf-8") as f:
        json.dump(analysis_doc, f, indent=1)
    with open(data_dir / EC_CSV_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(csv_rows(matrix_doc))


def summary_line(matrix_doc: dict[str, Any], analysis_doc: dict[str, Any]) -> str:
    """One-line human summary printed by the CLI."""
    return (f"{matrix_doc['total_proposals']:,} proposals · {matrix_doc['n_states']} states · "
            f"{matrix_doc['n_subsectors']} sub-sectors · {analysis_doc['n_subsectors']} analysed · "
            f"{matrix_doc['unclassified_activity']:,} unclassified")


def build(envelope: dict[str, Any], data_dir: Path = DATA_DIR,
          built: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Full pipeline: API envelope -> (matrix_doc, analysis_doc), written to ``data_dir``."""
    built = built or datetime.date.today().isoformat()
    agg = aggregate(envelope["data"])
    matrix_doc = matrix_document(agg, built)
    analysis_doc = subsector_analysis(agg, built)
    write_outputs(matrix_doc, analysis_doc, data_dir)
    return matrix_doc, analysis_doc
