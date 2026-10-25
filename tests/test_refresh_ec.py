"""Tests for scripts/refresh_ec.py — status bucketing, activity parsing, grant rate.

All fixtures are synthetic; nothing touches PARIVESH. build() writes into ROOT/data,
so ROOT is redirected to a tmp dir.
"""
import json

import pytest

from conftest import load

ec = load("refresh_ec")


@pytest.mark.parametrize("status,expected", [
    ("EC Granted", "granted"),
    ("ToR Granted", "tor_granted"),
    ("TOR granted", "tor_granted"),
    ("Delisted", "delisted"),
    ("Rejected", "dead"),
    ("Withdrawn by proponent", "dead"),
    ("Closed", "dead"),
    ("Lapsed", "dead"),
    ("Returned", "dead"),
    ("Under examination", "in_process"),
    ("", "in_process"),
    (None, "in_process"),
])
def test_bucket(status, expected):
    assert ec.bucket(status) == expected


def test_props_parses_label_value_pairs():
    r = {"other_property": json.dumps([{"label": "Activity", "value": "1(a) Mining of minerals"}])}
    assert ec.props(r) == {"Activity": "1(a) Mining of minerals"}


@pytest.mark.parametrize("raw", [None, "", "not json", "[{\"x\": 1}]"])
def test_props_bad_input_is_empty(raw):
    assert ec.props({"other_property": raw}) == {}


def _row(state, activity, status):
    return {"state": state, "proposalStatus": status,
            "other_property": json.dumps([{"label": "Activity", "value": activity}]) if activity else None}


def _build(tmp_path, monkeypatch, rows):
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(ec, "ROOT", str(tmp_path))
    ec.build({"data": rows})
    m = json.load(open(tmp_path / "data/ec_state_subsector_matrix.json"))
    a = json.load(open(tmp_path / "data/ec_subsector_analysis.json"))
    return m, {r["activity"]: r for r in a["subsector_analysis"]}


def _rows(code, label, **counts):
    out = []
    for status, n in counts.items():
        out += [_row("gujarat", f"{code} {label}", status)] * n
    return out


def test_build_matrix_counts_and_unclassified(tmp_path, monkeypatch):
    rows = _rows("5(f)", "Synthetic organic chemicals", **{"Granted": 3, "Rejected": 1})
    rows += [_row("rajasthan", None, "Granted"), _row(None, "garbage text", "Granted")]
    m, _ = _build(tmp_path, monkeypatch, rows)
    assert m["total_proposals"] == 6
    assert m["unclassified_activity"] == 2
    assert m["activity_labels"] == {"5(f)": "Synthetic organic chemicals"}
    cells = {(c["state"], c["activity"], c["status"]): c["count"] for c in m["matrix"]}
    assert cells[("GUJARAT", "5(f)", "granted")] == 3
    assert cells[("GUJARAT", "5(f)", "dead")] == 1
    assert cells[("RAJASTHAN", "UNCLASSIFIED", "granted")] == 1
    assert cells[("UNSPECIFIED", "garbage", "granted")] == 1


def test_subsector_needs_50_proposals(tmp_path, monkeypatch):
    rows = _rows("5(f)", "Chem", Granted=49)
    _, a = _build(tmp_path, monkeypatch, rows)
    assert a == {}


def test_grant_rate_excludes_only_delisted(tmp_path, monkeypatch):
    """README: 'Grant rate excludes delisted proposals from the denominator'.

    40 granted, 10 ToR, 20 in-process, 30 rejected/withdrawn, 100 delisted.
    Delisted is the only status the README excludes, so the rate is
    40 / (40 + 10 + 20 + 30) = 40.0%. The original code also dropped the 30
    rejected proposals and reported 40 / 70 = 57.1% — rejections never lowered it.
    """
    rows = _rows("8(a)", "Building and construction", **{
        "EC Granted": 40, "ToR Granted": 10, "Under examination": 20,
        "Rejected": 15, "Withdrawn": 15, "Delisted": 100})
    _, a = _build(tmp_path, monkeypatch, rows)
    rec = a["8(a)"]
    assert (rec["granted"], rec["tor_granted"], rec["in_process"], rec["dead"], rec["delisted"]) == (40, 10, 20, 30, 100)
    assert rec["grant_rate_pct"] == 40.0


def test_rejections_lower_the_grant_rate(tmp_path, monkeypatch):
    base = _rows("8(a)", "Construction", **{"EC Granted": 50, "Under examination": 50})
    more_rejects = base + _rows("8(a)", "Construction", Rejected=50)
    _, a1 = _build(tmp_path, monkeypatch, base)
    (tmp_path / "data").rename(tmp_path / "data_old")
    _, a2 = _build(tmp_path, monkeypatch, more_rejects)
    assert a2["8(a)"]["grant_rate_pct"] < a1["8(a)"]["grant_rate_pct"]


def test_top_states_shares(tmp_path, monkeypatch):
    rows = [_row("gujarat", "5(f) Chem", "Granted")] * 30 + [_row("maharashtra", "5(f) Chem", "Granted")] * 10
    rows += [_row("odisha", "5(f) Chem", "Rejected")] * 20
    _, a = _build(tmp_path, monkeypatch, rows)
    top = a["5(f)"]["top_states"]
    assert top[0] == {"state": "Gujarat", "granted": 30, "share_pct": 75.0}
    assert top[1] == {"state": "Maharashtra", "granted": 10, "share_pct": 25.0}
    assert len(top) == 2   # a state with no grants is not a leader
