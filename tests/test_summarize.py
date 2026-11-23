"""summarize.py: headline totals, the six consistency checks and the --old drop guard (synthetic snapshots)."""
import copy
import json

import pytest
import synth
from conftest import load

sm = load("summarize")


@pytest.fixture
def snap(tmp_path):
    return synth.write_snapshot(str(tmp_path / "new"))


def run_main(monkeypatch, capsys, *argv):
    monkeypatch.setattr("sys.argv", ["summarize.py", *argv])
    with pytest.raises(SystemExit) as e:
        sm.main()
    cap = capsys.readouterr()
    return e.value.code, cap.out, cap.err


def test_summarize_totals_and_leaders(snap):
    s = sm.summarize(snap)
    m = synth.matrix()
    assert s["ec_total_proposals"] == m["total_proposals"] == s["matrix_cell_total"] == s["csv_total"] == s["state_totals_sum"]
    assert s["matrix_by_status"] == {"granted": 10, "in_process": 2, "dead": 1, "delisted": 4, "tor_granted": 2}
    assert s["top_states"][0] == ("Goa", 10) and s["top_subsectors"][0][:3] == ("1(a)", "Mining of minerals", 15)
    assert s["other_clearances"]["FC"]["total"] == 12 and s["other_clearances"]["FC"]["granted"] == 6
    assert s["other_clearances"]["FC"]["grant_rate"] == 85.7
    assert all(s["checks"].values()) and len(s["checks"]) == 6


def test_top_lists_are_capped_at_five_and_sorted(tmp_path):
    a = synth.analysis()
    a["state_totals"] = [{"state": f"S{i}", "total": i} for i in range(8)]
    a["subsector_analysis"] = a["subsector_analysis"] * 4
    d = synth.write_snapshot(str(tmp_path), a=a)
    s = sm.summarize(d)
    assert [t for _, t in s["top_states"]] == [7, 6, 5, 4, 3] and len(s["top_subsectors"]) == 5
    assert s["top_subsectors"][0][2] >= s["top_subsectors"][-1][2]


@pytest.mark.parametrize("mutate,failing", [
    ("csv", "matrix total == csv total"),
    ("state_totals", "state_totals sum == total_proposals"),
    ("unclassified_high", "unclassified < total_proposals"),
    ("unclassified_negative", "unclassified < total_proposals"),
    ("subsector_parts", "subsector status parts == subsector total"),
    ("funnel_parts", "FC/WL/CRZ funnel parts == total"),
    ("total_proposals", "matrix total == total_proposals"),
])
def test_each_consistency_check_can_fail_on_its_own(tmp_path, mutate, failing):
    m, a, o = synth.matrix(), synth.analysis(), synth.other()
    kw = {}
    if mutate == "csv":
        kw["csv_total"] = 1
    elif mutate == "state_totals":
        a["state_totals"][0]["total"] += 1
    elif mutate == "unclassified_high":
        m["unclassified_activity"] = m["total_proposals"]
    elif mutate == "unclassified_negative":
        m["unclassified_activity"] = -1
    elif mutate == "subsector_parts":
        a["subsector_analysis"][0]["total"] += 1
    elif mutate == "funnel_parts":
        o["clearances"]["CRZ"]["total"] += 1
    elif mutate == "total_proposals":
        m["total_proposals"] += 1
    d = synth.write_snapshot(str(tmp_path), m=m, a=a, o=o, **kw)
    checks = sm.summarize(d)["checks"]
    assert checks[failing] is False
    only = {"total_proposals": ["matrix total == total_proposals", "state_totals sum == total_proposals"]}.get(mutate, [failing])
    assert [k for k, v in checks.items() if not v] == only


def test_unclassified_zero_is_allowed(tmp_path):
    m = synth.matrix()
    m["unclassified_activity"] = 0
    assert sm.summarize(synth.write_snapshot(str(tmp_path), m=m))["checks"]["unclassified < total_proposals"] is True


def test_headlines_keys(snap):
    h = sm.headlines(sm.summarize(snap))
    assert h["EC proposals"] == 19 and h["matrix total"] == 19 and h["EC granted"] == 10
    assert h["FC total"] == 12 and h["FC granted"] == 6 and h["WLC total"] == 6 and h["CRZ granted"] == 2


def test_main_ok_prints_json_and_pass_lines(snap, monkeypatch, capsys):
    code, out, err = run_main(monkeypatch, capsys, snap)
    assert code == 0 and json.loads(out)["ec_total_proposals"] == 19
    assert err.count("[PASS]") == 6 and "[FAIL]" not in err and "OK to commit" in err


def test_main_exits_1_on_failed_check(tmp_path, monkeypatch, capsys):
    d = synth.write_snapshot(str(tmp_path), csv_total=5)
    code, _, err = run_main(monkeypatch, capsys, d)
    assert code == 1 and "[FAIL] matrix total == csv total" in err and "NOT OK" in err


def make_old(tmp_path, scale):
    m = synth.matrix()
    for c in m["matrix"]:
        c["count"] = c["count"] * scale
    m["total_proposals"] = sum(c["count"] for c in m["matrix"])
    a = synth.analysis(m)
    o = copy.deepcopy(synth.other())
    return synth.write_snapshot(str(tmp_path / "old"), m=m, a=a, o=o)


def test_old_snapshot_drop_guard(snap, tmp_path, monkeypatch, capsys):
    old_same = make_old(tmp_path, 1)
    code, out, _ = run_main(monkeypatch, capsys, snap, "--old", old_same)
    assert code == 0 and "<-- DROP" not in out and "EC proposals" in out
    old_bigger = make_old(tmp_path / "x", 2)                       # new is 50% smaller than old -> every headline drops
    code, out, err = run_main(monkeypatch, capsys, snap, "--old", old_bigger)
    assert code == 1 and "<-- DROP" in out and "NOT OK" in err
    code, out, _ = run_main(monkeypatch, capsys, snap, "--old", old_bigger, "--max-drop", "60")
    assert code == 0 and "<-- DROP" not in out                     # -50% is within a 60% allowance


def scaled(tmp_path, k):
    m = synth.matrix()
    for c in m["matrix"]:
        c["count"] *= k
    m["total_proposals"] = sum(c["count"] for c in m["matrix"])
    return synth.write_snapshot(str(tmp_path), m=m, a=synth.analysis(m))


def test_drop_threshold_is_strict(tmp_path, monkeypatch, capsys):
    new, old = scaled(tmp_path / "n", 4), scaled(tmp_path / "o", 5)           # new is exactly 80% of old on EC headlines
    code, out, _ = run_main(monkeypatch, capsys, new, "--old", old, "--max-drop", "20")
    ec_lines = [ln for ln in out.splitlines() if ln.startswith("EC ") or ln.startswith("matrix")]
    assert ec_lines and not any("DROP" in ln for ln in ec_lines)             # exactly -20.0% is not 'more than 20%'
    code, out, _ = run_main(monkeypatch, capsys, new, "--old", old, "--max-drop", "19.9")
    assert code == 1 and "<-- DROP" in out


def test_new_headline_absent_from_old_is_infinite_growth(snap, tmp_path, monkeypatch, capsys):
    o = synth.other()
    del o["clearances"]["CRZ"]
    old = synth.write_snapshot(str(tmp_path / "o"), o=o)
    code, out, _ = run_main(monkeypatch, capsys, snap, "--old", old)
    assert code == 0 and "inf%" in out


def test_default_allowance_is_twenty_percent(tmp_path, monkeypatch, capsys):
    new, old = scaled(tmp_path / "n", 17), scaled(tmp_path / "o", 20)          # -15% on every EC headline
    code, out, _ = run_main(monkeypatch, capsys, new, "--old", old)
    ec_lines = [ln for ln in out.splitlines() if ln.startswith(("EC ", "matrix"))]
    assert ec_lines and not any("DROP" in ln for ln in ec_lines)               # inside the default 20% allowance
    assert "-15.0%" in out


def test_headline_that_is_zero_in_both_snapshots_is_unchanged(tmp_path, monkeypatch, capsys):
    o = synth.other()
    o["clearances"]["CRZ"]["funnel"] = {"in_process": 4}
    o["clearances"]["CRZ"]["total"] = 4
    new = synth.write_snapshot(str(tmp_path / "n"), o=o)
    old = synth.write_snapshot(str(tmp_path / "o"), o=o)
    code, out, _ = run_main(monkeypatch, capsys, new, "--old", old)
    line = next(ln for ln in out.splitlines() if ln.startswith("CRZ granted"))
    assert line.split()[-1] == "0.0%" and code == 0
