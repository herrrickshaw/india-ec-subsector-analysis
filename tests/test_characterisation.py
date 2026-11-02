"""Golden tests: the refactored pipeline reproduces the pre-refactor outputs byte for byte.

tests/fixtures/expected/* were produced by the original scripts on the synthetic
dumps in tests/fixtures/input/ (built date FIXTURE_BUILT).
"""
from __future__ import annotations

import build_other_clearances
import build_page
from conftest import FIXTURE_BUILT

from ec_analysis import ec
from ec_analysis import other_clearances as oc
from ec_analysis.parivesh import load_dump


def test_ec_pipeline_matches_golden(tmp_path, fixture_input, fixture_expected):
    ec.build(load_dump(fixture_input / "ec.json"), data_dir=tmp_path, built=FIXTURE_BUILT)
    for name in ("ec_state_subsector_matrix.json", "ec_subsector_analysis.json", "ec_state_subsector.csv"):
        assert (tmp_path / name).read_bytes() == (fixture_expected / name).read_bytes(), name


def test_other_clearances_matches_golden(tmp_path, fixture_input, fixture_expected):
    report = oc.build_report(lambda t: load_dump(fixture_input / f"parivesh_type{t}.json")["data"], built=FIXTURE_BUILT)
    path = oc.write_report(report, tmp_path)
    assert path.read_bytes() == (fixture_expected / "parivesh_other_clearances.json").read_bytes()


def test_index_html_matches_golden(fixture_expected):
    an, mx = build_page.load_inputs(fixture_expected)
    assert build_page.render(an, mx, today=FIXTURE_BUILT) == (fixture_expected / "index.html").read_text()


def test_other_clearances_html_matches_golden(fixture_expected):
    report = build_other_clearances.load_report(fixture_expected)
    assert build_other_clearances.render(report, today=FIXTURE_BUILT) == (fixture_expected / "other_clearances.html").read_text()
