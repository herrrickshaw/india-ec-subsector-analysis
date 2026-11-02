"""Smoke tests: each scripts/*.py entry point runs end to end on the fixtures (offline)."""
from __future__ import annotations

import subprocess
import sys

from conftest import ROOT

SCRIPTS = ROOT / "scripts"


def run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, check=True, cwd=ROOT)


def test_refresh_then_build_ec(tmp_path, fixture_input):
    out = run(SCRIPTS / "refresh_ec.py", "--from", fixture_input / "ec.json", "--data-dir", tmp_path)
    assert out.stdout.strip() == "500 proposals · 7 states · 5 sub-sectors · 5 analysed · 129 unclassified"
    html = tmp_path / "index.html"
    out = run(SCRIPTS / "build_page.py", "--data-dir", tmp_path, "--out", html)
    assert "5 sub-sectors, 7 states" in out.stdout
    assert html.read_text().startswith("<!doctype html>")


def test_refresh_then_build_other(tmp_path, fixture_input):
    out = run(SCRIPTS / "refresh_other_clearances.py", "--from-dir", fixture_input, "--data-dir", tmp_path)
    assert out.stdout.splitlines()[0].startswith("FC: 120 proposals")
    assert out.stdout.splitlines()[-1].startswith("wrote ")
    html = tmp_path / "other.html"
    out = run(SCRIPTS / "build_other_clearances.py", "--data-dir", tmp_path, "--out", html)
    assert "FC/WL/CRZ, forest granted" in out.stdout
    assert html.read_text().startswith("<!doctype html>")


def test_help_for_every_entry_point():
    for name in ("refresh_ec.py", "refresh_other_clearances.py", "build_page.py", "build_other_clearances.py"):
        assert run(SCRIPTS / name, "--help").returncode == 0
