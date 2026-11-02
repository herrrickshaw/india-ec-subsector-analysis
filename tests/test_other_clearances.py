"""Unit tests for the Forest / Wildlife / CRZ aggregation on tiny synthetic rows."""
from __future__ import annotations

import pytest

from ec_analysis import other_clearances as oc


@pytest.mark.parametrize("raw,expected", [("12.5", 12.5), ("1,234.75", 1234.75), (7, 7.0), ("", None), (None, None), ("abc", None)])
def test_parse_number(raw, expected):
    assert oc.parse_number(raw) == expected


@pytest.mark.parametrize("status,kind,expected", [
    ("Delisted", "FC", "delisted"),
    ("Removed", "WLC", "dead"),
    ("Final Diversion Order Issued", "FC", "granted"),
    ("Stage-II Accorded", "FC", "granted"),
    ("Stage-I Accorded", "FC", "in_process"),
    ("Pending at Proponent", "FC", "in_process"),
    ("Rejected", "FC", "dead"),
    ("Recommended by NBWL", "WLC", "granted"),
    ("Not Recommended", "WLC", "in_process"),
    ("Disposed", "WLC", "granted"),
    ("Withdrawn", "WLC", "dead"),
    ("CRZ Granted", "CRZ", "granted"),
    ("Returned", "CRZ", "dead"),
    ("Pending at SEIAA", "CRZ", "in_process"),
    (None, "CRZ", "in_process"),
])
def test_bucket_status(status, kind, expected):
    assert oc.bucket_status(status, kind) == expected


FC_ROWS = [
    {"state": "Madhya Pradesh", "proposalStatus": "Final Diversion Order Issued", "forest_area": "100",
     "clearanceType": "Form-A fresh", "nameOfUserAgency": "NHAI"},
    {"state": "madhya pradesh", "proposalStatus": "Stage-I Accorded", "forest_area": "1,000",
     "clearanceType": "Form-B renewal", "nameOfUserAgency": "NHAI"},
    {"state": "Assam", "proposalStatus": "Rejected", "forest_area": "abc", "clearanceType": "Form-E x",
     "nameOfUserAgency": None},
    {"state": None, "proposalStatus": "Delisted", "forest_area": "5", "clearanceType": None,
     "nameOfUserAgency": "Coal India"},
]


def test_summarise_forest_register():
    rec = oc.summarise_register(FC_ROWS, "FC", "Forest Clearance")
    assert rec["total"] == 4 and rec["n_states"] == 3
    assert rec["funnel"] == {"granted": 1, "in_process": 1, "dead": 1, "delisted": 1}
    assert rec["grant_rate_pct_of_decided"] == 50.0  # dead + delisted excluded
    assert rec["top_states"][0] == {"state": "Madhya Pradesh", "total": 2, "granted": 1, "pending": 1}
    fa = rec["forest_area_ha"]
    assert fa["pipeline_total"] == 1105 and fa["granted"] == 100
    assert fa["acres_granted"] == round(100 * oc.HA_TO_ACRE)
    assert rec["forest_area_by_state"][0] == {"state": "Madhya Pradesh", "pipeline_ha": 1100, "granted_ha": 100,
                                              "granted_acres": 247}
    assert rec["by_form_type"]["fresh_diversion_FormA"] == 1
    assert rec["by_form_type"]["renewal_FormBD"] == 1
    assert rec["by_form_type"]["re_diversion_FormE"] == 1
    assert rec["by_form_type"]["transfer_FormF"] == 0
    agencies = {a["agency"]: a["proposals"] for a in rec["top_user_agencies"]}
    assert agencies == {"NHAI": 2, "Coal India": 1}  # "?" placeholder is dropped


def test_summarise_non_forest_has_no_area_fields():
    rec = oc.summarise_register([{"state": "Goa", "proposalStatus": "CRZ Granted"}], "CRZ", "CRZ Clearance")
    assert rec["grant_rate_pct_of_decided"] == 100.0
    assert "forest_area_ha" not in rec


def test_summarise_empty_register():
    rec = oc.summarise_register([], "WLC", "Wildlife Clearance")
    assert rec["total"] == 0 and rec["grant_rate_pct_of_decided"] is None and rec["top_states"] == []


def test_build_report_uses_row_source_per_type(tmp_path):
    calls = []

    def get_rows(t):
        calls.append(t)
        return FC_ROWS if t == 2 else []

    report = oc.build_report(get_rows, built="2026-01-01")
    assert calls == [2, 3, 4]
    assert list(report) == ["built", "source", "note", "method", "clearances"]
    assert set(report["clearances"]) == {"FC", "WLC", "CRZ"}
    assert oc.summary_line(report["clearances"]["FC"]).startswith("FC: 4 proposals | grant% 50.0 | 3 states | forest granted 100 ha")
    path = oc.write_report(report, tmp_path)
    assert path.name == "parivesh_other_clearances.json" and path.exists()
