"""Tests for scripts/refresh_other_clearances.py — per-type bucketing and grant rates.

Synthetic rows only; get_rows is injected, so no PARIVESH call is made.
"""
import json

import pytest

from conftest import load

oc = load("refresh_other_clearances")


@pytest.mark.parametrize("status,kind,expected", [
    ("Final Diversion Order Issued", "FC", "granted"),
    ("Stage-II Accorded", "FC", "granted"),
    ("Stage-I Accorded", "FC", "in_process"),     # in-principle is not a grant
    ("Pending at State", "FC", "in_process"),
    ("Rejected", "FC", "dead"),
    ("Returned to user agency", "FC", "dead"),
    ("Delisted", "FC", "delisted"),
    ("removed", "WLC", "dead"),
    ("Recommended by NBWL", "WLC", "granted"),
    ("Disposed", "WLC", "granted"),
    ("Withdrawn", "WLC", "dead"),
    ("Pending at Proponent", "WLC", "in_process"),
    ("CRZ Clearance Granted", "CRZ", "granted"),
    ("Closed", "CRZ", "dead"),
    (None, "CRZ", "in_process"),
])
def test_bucket(status, kind, expected):
    assert oc.bucket(status, kind) == expected


def test_wlc_not_recommended_is_not_granted():
    assert oc.bucket("Not Recommended", "WLC") != "granted"


@pytest.mark.parametrize("raw,expected", [("1,234.5", 1234.5), ("0", 0.0), (None, None), ("n/a", None)])
def test_num(raw, expected):
    assert oc.num(raw) == expected


def _build(tmp_path, monkeypatch, rows_by_type):
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(oc, "ROOT", str(tmp_path))
    oc.build(lambda t: rows_by_type.get(t, []))
    return json.load(open(tmp_path / "data/parivesh_other_clearances.json"))["clearances"]


def _rows(status, n, **extra):
    return [dict({"proposalStatus": status, "state": "odisha"}, **extra)] * n


def test_grant_rate_of_decided_uses_decided_proposals(tmp_path, monkeypatch):
    """The output key and the page both say 'grant rate of decided'.

    CRZ fixture: 30 granted, 10 rejected (decided = 40), 60 in-process, 20 delisted.
    Of decided = 30 / 40 = 75.0%. The original code divided by granted + in-process
    (30 / 90 = 33.3%): undecided proposals in, rejected ones out — the opposite of 'decided'.
    """
    rows = _rows("Granted", 30) + _rows("Rejected", 10) + _rows("Under process", 60) + _rows("Delisted", 20)
    c = _build(tmp_path, monkeypatch, {4: rows})["CRZ"]
    assert c["funnel"] == {"granted": 30, "dead": 10, "in_process": 60, "delisted": 20}
    assert c["grant_rate_pct_of_decided"] == 75.0


def test_rejections_lower_grant_rate_of_decided(tmp_path, monkeypatch):
    rows = _rows("Granted", 30) + _rows("Under process", 60)
    worse = rows + _rows("Rejected", 30)
    a = _build(tmp_path, monkeypatch, {4: rows})["CRZ"]["grant_rate_pct_of_decided"]
    (tmp_path / "data").rename(tmp_path / "d0")
    b = _build(tmp_path, monkeypatch, {4: worse})["CRZ"]["grant_rate_pct_of_decided"]
    assert b < a


def test_empty_register_gives_none(tmp_path, monkeypatch):
    c = _build(tmp_path, monkeypatch, {})
    assert c["WLC"]["total"] == 0 and c["WLC"]["grant_rate_pct_of_decided"] is None


def test_forest_area_granted_vs_pipeline(tmp_path, monkeypatch):
    rows = (_rows("Final Diversion Order Issued", 2, forest_area="10.5", clearanceType="Form-A fresh")
            + _rows("Pending at State", 1, forest_area="100", clearanceType="Form-E rediv")
            + _rows("Delisted", 1, forest_area="1,000", clearanceType="Form-B renewal")
            + _rows("Rejected", 1, forest_area="bad", clearanceType="Form-F"))
    fc = _build(tmp_path, monkeypatch, {2: rows})["FC"]
    assert fc["forest_area_ha"]["granted"] == 21
    assert fc["forest_area_ha"]["pipeline_total"] == 1121
    assert fc["forest_area_ha"]["acres_granted"] == round(21 * 2.47105)
    assert fc["by_form_type"] == {**fc["by_form_type"], "fresh_diversion_FormA": 2, "re_diversion_FormE": 1,
                                  "renewal_FormBD": 1, "transfer_FormF": 1}
