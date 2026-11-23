"""build_page.py and build_other_clearances.py render static HTML from the JSON snapshot.
Synthetic snapshot in a tmp ROOT; nothing touches the repo's docs/."""
import os

import pytest
import synth
from conftest import load


@pytest.fixture
def root(tmp_path):
    synth.write_snapshot(str(tmp_path))
    return tmp_path


def run(name, root):
    mod = load(name)
    mod.ROOT = str(root)
    mod.main()
    return mod


def test_build_page_writes_index_with_totals_and_rows(root, capsys):
    run("build_page", root)
    html = open(root / "docs" / "index.html").read()
    m = synth.matrix()
    assert html.startswith("<!doctype html>") and f"<b>{m['total_proposals']:,}" in html
    assert f'<div class="n">{m["total_proposals"]:,}</div><div class="l">EC proposals</div>' in html
    assert '<div class="n">2</div><div class="l">sub-sectors analysed</div>' in html
    granted = sum(c["count"] for c in m["matrix"] if c["status"] == "granted")
    assert f'<div class="n">{granted:,}</div><div class="l">clearances granted</div>' in html
    assert html.count('<tr data-act="') == 2
    assert capsys.readouterr().out.strip() == f"docs/index.html: 2 sub-sectors, {m['n_states']} states, client-side repivot"


def test_build_page_embeds_the_pivot_matrix_for_client_side_filtering(root):
    run("build_page", root)
    html = open(root / "docs" / "index.html").read()
    import json
    line = next(ln for ln in html.splitlines() if ln.startswith("const PIV="))
    piv = json.loads(line[len("const PIV="):].rstrip(";"))
    assert piv == {"1(a)": {"GOA": {"granted": 6, "in_process": 2}, "KERALA": {"granted": 3, "delisted": 4}},
                   "5(f)": {"GOA": {"granted": 1, "dead": 1}, "KERALA": {"tor_granted": 2}}}
    labels = json.loads(next(ln for ln in html.splitlines() if ln.startswith("const LABELS=")).split("=", 1)[1].rstrip(";"))
    assert labels == {"1(a)": "Mining of minerals", "5(f)": "Synthetic organic chemicals"}


@pytest.mark.parametrize("gr,cls", [(65.0, "hi"), (64.9, ""), (40.0, ""), (39.9, "lo"), (100.0, "hi")])
def test_grant_rate_colour_thresholds(tmp_path, gr, cls):
    a = synth.analysis()
    a["subsector_analysis"][0]["grant_rate_pct"] = gr
    synth.write_snapshot(str(tmp_path), a=a)
    run("build_page", tmp_path)
    html = open(tmp_path / "docs" / "index.html").read()
    first = next(line for line in html.splitlines() if 'data-act="1(a)"' in line)
    assert f'<td class="num pct {cls}">{gr:.0f}%</td>' in first


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="`grcls = 'hi' if gr and gr >= 65 else 'lo' if gr and gr < 40 else ''` treats a 0.0% grant "
                          "rate as falsy, so the worst possible rate gets no 'lo' class (the client-side JS gives 'lo')")
def test_zero_percent_grant_rate_is_flagged_low(tmp_path):
    a = synth.analysis()
    a["subsector_analysis"][0]["grant_rate_pct"] = 0.0
    synth.write_snapshot(str(tmp_path), a=a)
    run("build_page", tmp_path)
    first = next(ln for ln in open(tmp_path / "docs" / "index.html").read().splitlines() if 'data-act="1(a)"' in ln)
    assert '<td class="num pct lo">0%</td>' in first


@pytest.mark.xfail(strict=True, raises=TypeError,
                   reason="refresh_ec.build() emits grant_rate_pct = None for a sub-sector whose proposals are all "
                          "delisted (live == 0), but build_page formats it with f'{gr:.0f}%' -> TypeError; the "
                          "client-side JS already handles null")
def test_build_page_survives_a_subsector_with_no_live_proposals(tmp_path):
    a = synth.analysis()
    a["subsector_analysis"][0]["grant_rate_pct"] = None
    synth.write_snapshot(str(tmp_path), a=a)
    run("build_page", tmp_path)


def test_build_other_clearances_page(root, capsys):
    run("build_other_clearances", root)
    html = open(root / "docs" / "other_clearances.html").read()
    o = synth.other()["clearances"]
    assert f'<div class="cbig">{o["FC"]["total"]:,}</div>' in html
    assert "400 ha" in html and "988" in html                                 # granted forest area, ha and acres
    assert "PWD" in html and "fresh (Form-A)" in html
    assert f"Granted, of decided: <b>{o['FC']['grant_rate_pct_of_decided']}%</b>" in html
    out = capsys.readouterr().out
    assert out.strip() == "docs/other_clearances.html: FC/WL/CRZ, forest granted 400 ha"


def test_funnel_bar_widths_sum_to_the_non_empty_segments(root):
    run("build_other_clearances", root)
    html = open(root / "docs" / "other_clearances.html").read()
    import re
    bar = re.search(r'<div class="bar">(.*?)</div>', html, re.S).group(1)       # FC: granted 6, in_process 3, dead 1, delisted 2 of 12
    widths = [float(w) for w in re.findall(r"width:([\d.]+)%", bar)]
    assert widths == [50.0, 25.0, 8.33, 16.67] and abs(sum(widths) - 100) < 0.05


def test_funnel_bar_skips_absent_statuses(root):
    run("build_other_clearances", root)
    html = open(root / "docs" / "other_clearances.html").read()
    import re
    bars = re.findall(r'<div class="bar">(.*?)</div>', html, re.S)
    wl = bars[1]                                                               # WLC funnel has no 'dead'/'delisted'
    assert wl.count("<span") == 2 and "dead" not in wl and "delisted" not in wl


def test_zero_total_clearance_would_divide_by_zero(tmp_path):
    o = synth.other()
    o["clearances"]["CRZ"]["funnel"] = {"granted": 0}
    o["clearances"]["CRZ"]["total"] = 0
    synth.write_snapshot(str(tmp_path), o=o)
    mod = load("build_other_clearances")
    mod.ROOT = str(tmp_path)
    mod.main()                                                                 # funnel_bar skips falsy statuses, so total=0 is safe
    assert os.path.exists(tmp_path / "docs" / "other_clearances.html")


def test_state_table_lists_the_twelve_largest_states(tmp_path):
    a = synth.analysis()
    a["state_totals"] = [{"state": f"State{i:02d}", "total": 100 - i} for i in range(15)]
    synth.write_snapshot(str(tmp_path), a=a)
    run("build_page", tmp_path)
    html = open(tmp_path / "docs" / "index.html").read()
    assert "State11" in html and "State12" not in html                           # first 12 only
    assert html.index("State00") < html.index("State01")


def test_both_states_of_the_small_fixture_are_listed(root):
    run("build_page", root)
    html = open(root / "docs" / "index.html").read()
    assert "<td>Goa</td>" in html and "<td>Kerala</td>" in html
