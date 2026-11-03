"""Unit tests for the pure EC aggregation functions on tiny synthetic rows."""
from __future__ import annotations

import json

import pytest

from ec_analysis import ec


@pytest.mark.parametrize("status,expected", [
    ("EC Granted", "granted"),
    ("ToR Granted", "tor_granted"),
    ("Delisted", "delisted"),
    ("Rejected", "dead"),
    ("Withdrawn", "dead"),
    ("Closed", "dead"),
    ("Lapsed", "dead"),
    ("Returned", "dead"),
    ("Pending at Proponent", "in_process"),
    ("", "in_process"),
    (None, "in_process"),
])
def test_bucket_status(status, expected):
    assert ec.bucket_status(status) == expected


def test_parse_activity_code_and_label():
    assert ec.parse_activity("1(a) Mining of minerals") == ("1(a)", "Mining of minerals")
    assert ec.parse_activity("  5(f)   Synthetic organic chemicals ") == ("5(f)", "Synthetic organic chemicals")
    assert ec.parse_activity("Misc something") == ("Misc", None)
    assert ec.parse_activity("   ") == (ec.UNCLASSIFIED, None)


def test_parse_activity_truncates_label():
    code, label = ec.parse_activity("3(a) " + "x" * 100)
    assert code == "3(a)" and len(label) == 60


def test_parse_properties():
    row = {"other_property": json.dumps([{"label": "Activity", "value": "1(a) Mining"}, {"label": "Category", "value": "B2"}])}
    assert ec.parse_properties(row) == {"Activity": "1(a) Mining", "Category": "B2"}
    assert ec.parse_properties({"other_property": "not-json"}) == {}
    assert ec.parse_properties({"other_property": None}) == {}
    assert ec.parse_properties({}) == {}
    assert ec.parse_properties({"other_property": json.dumps([{"nolabel": 1}])}) == {}
    assert ec.parse_properties({"other_property": json.dumps({"a": 1})}) == {}


def _row(state, activity, status):
    return {"state": state, "proposalStatus": status,
            "other_property": json.dumps([{"label": "Activity", "value": activity}])}


TINY = [
    _row("Rajasthan", "1(a) Mining of minerals", "EC Granted"),
    _row("rajasthan ", "1(a) Mining of minerals", "EC Granted"),
    _row("Gujarat", "1(a) Mining of minerals", "Rejected"),
    _row("Gujarat", "5(f) Synthetic organic chemicals", "Delisted"),
    _row("Gujarat", "5(f) Synthetic organic chemicals", "ToR Granted"),
    _row(None, "no code here", "Pending"),
    _row("Odisha", "", "EC Granted"),
]


def test_aggregate_counts_states_and_unclassified():
    agg = ec.aggregate(TINY)
    assert agg.n_rows == 7
    assert agg.unclassified == 2
    assert agg.activity_labels == {"1(a)": "Mining of minerals", "5(f)": "Synthetic organic chemicals"}
    assert agg.matrix[("RAJASTHAN", "1(a)", "granted")] == 2
    assert agg.matrix[("GUJARAT", "1(a)", "dead")] == 1
    assert agg.matrix[("UNSPECIFIED", "no", "in_process")] == 1
    assert agg.matrix[("ODISHA", ec.UNCLASSIFIED, "granted")] == 1


def test_matrix_document_shape():
    doc = ec.matrix_document(ec.aggregate(TINY), built="2026-01-01")
    assert doc["built"] == "2026-01-01"
    assert doc["total_proposals"] == 7
    assert doc["n_states"] == 4
    assert doc["n_subsectors"] == 2
    assert doc["unclassified_activity"] == 2
    cells = [(c["state"], c["activity"], c["status"]) for c in doc["matrix"]]
    assert cells == sorted(cells)
    assert sum(c["count"] for c in doc["matrix"]) == 7


def test_subsector_analysis_grant_rate_and_threshold(monkeypatch):
    monkeypatch.setattr(ec, "EC_MIN_SUBSECTOR_TOTAL", 1)
    doc = ec.subsector_analysis(ec.aggregate(TINY), built="2026-01-01")
    by_code = {s["activity"]: s for s in doc["subsector_analysis"]}
    # UNCLASSIFIED and codes without ")" are never analysed
    assert set(by_code) == {"1(a)", "5(f)"}
    mining = by_code["1(a)"]
    assert mining["total"] == 3 and mining["granted"] == 2 and mining["dead"] == 1
    assert mining["grant_rate_pct"] == 100.0  # dead is not in the live denominator
    assert mining["top_states"] == [{"state": "Rajasthan", "granted": 2, "share_pct": 100.0}]
    chem = by_code["5(f)"]
    assert chem["delisted"] == 1 and chem["tor_granted"] == 1
    assert chem["grant_rate_pct"] == 0.0  # live = tor_granted only
    assert doc["state_totals"][0] == {"state": "Gujarat", "total": 3}


def test_subsector_analysis_default_threshold_drops_small_subsectors():
    doc = ec.subsector_analysis(ec.aggregate(TINY), built="2026-01-01")
    assert doc["subsector_analysis"] == [] and doc["n_subsectors"] == 0


def test_csv_rows_header_and_labels():
    doc = ec.matrix_document(ec.aggregate(TINY), built="x")
    rows = list(ec.csv_rows(doc))
    assert rows[0] == ["state", "activity_code", "activity_label", "status", "count"]
    assert len(rows) == 1 + len(doc["matrix"])
    assert ["RAJASTHAN", "1(a)", "Mining of minerals", "granted", 2] in rows
    assert ["ODISHA", ec.UNCLASSIFIED, "", "granted", 1] in rows


def test_build_writes_three_files(tmp_path):
    matrix_doc, analysis_doc = ec.build({"data": TINY}, data_dir=tmp_path, built="2026-01-01")
    assert {p.name for p in tmp_path.iterdir()} == {
        "ec_state_subsector_matrix.json", "ec_subsector_analysis.json", "ec_state_subsector.csv"}
    assert json.loads((tmp_path / "ec_state_subsector_matrix.json").read_text()) == matrix_doc
    assert "7 proposals · 4 states · 2 sub-sectors · 0 analysed · 2 unclassified" == ec.summary_line(matrix_doc, analysis_doc)
