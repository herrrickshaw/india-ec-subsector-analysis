"""build_ec_library.py: source readers, status bucketing, the unified view and the ec_search macro,
built into a tmp LIB from tiny synthetic p2 / dashboard / legacy sources."""
import gzip
import json
import os

import pytest
from conftest import load

duckdb = pytest.importorskip("duckdb")
lib = load("build_ec_library")


def op(activity=None, proposal_for=None):
    props = []
    if activity:
        props.append({"label": "Activity", "value": activity})
    if proposal_for:
        props.append({"label": "Proposal For", "value": proposal_for})
    return json.dumps(props)


P2 = {"data": [
    {"proposalNo": "P1", "projectName": "Bio Diesel Plant", "nameOfUserAgency": "Acme Fuels", "state": " goa ",
     "proposalStatus": "EC Granted", "category": "A", "sector": "Industry", "issuing_authority": "MoEF",
     "dateOfSubmission": "2024-03-05T10:00:00", "certificate_url": "u", "other_property": op("5(f) Synthetic organic chemicals", "Fresh")},
    {"proposalNo": "P2", "projectName": "Solar Park", "nameOfUserAgency": "Sun Co", "state": "Kerala",
     "proposalStatus": "Rejected", "other_property": "not json"},
    {"proposalNo": None, "projectName": "orphan", "state": "Goa", "proposalStatus": "ToR Granted", "other_property": op("1(a) Mining")},
]}
DASH = {"data": [
    {"proposal_no": "D1", "project_name": "Old name", "name_of_proponent": "First", "state_name": "goa", "status": "Delisted"},
    {"proposal_no": "D1", "project_name": "Biodiesel Hub", "proponent": "Second", "state_name": " Goa ", "status": "Granted",
     "sector_name": "Energy", "submit_date": "2025-01-02T00:00:00", "granted_date": "2025-02-03T00:00:00"},
    {"proposal_no": "P1", "project_name": "Dup of p2", "state_name": "Goa", "status": "Granted", "start_date": "2025-05-06"},
]}
LEGACY = [
    ("Rpn_GA", [{"proposal_no": "IA/GA/IND2/123/2012", "file_no": "F1", "project": "Legacy Bio-diesel", "company": "Old Co", "status": "Rejected"},
                {"proposal_no": None, "file_no": "F2", "project": "No number", "company": "x", "status": "Granted"}]),
    ("C_D_KL", [{"proposal_no": "IA/KL/MIN/9/2010", "file_no": "F3", "project": "Mine", "company": "M", "status": "Granted"}]),
]


@pytest.fixture
def sources(tmp_path):
    p2, dash = tmp_path / "p2.json.gz", tmp_path / "dash.json"
    with gzip.open(p2, "wt") as f:
        json.dump(P2, f)
    dash.write_text(json.dumps(DASH))
    leg = tmp_path / "legacy"
    leg.mkdir()
    for name, rows in LEGACY:
        (leg / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    return str(p2), str(dash), str(leg)


@pytest.mark.parametrize("status,expected", [
    ("EC Granted", "granted"), ("ToR Granted", "tor_granted"), ("tor GRANTED", "tor_granted"), ("Delisted", "delisted"),
    ("Deleted", "delisted"), ("Rejected", "dead"), ("Withdrawn", "dead"), ("Closed", "dead"), ("Lapsed", "dead"),
    ("Returned", "dead"), ("EDS raised", "in_process"), ("", "in_process"), (None, "in_process"),
])
def test_bucket(status, expected):
    assert lib.bucket(status) == expected


def test_bucket_matches_refresh_ec_on_every_shared_status():
    ec = load("refresh_ec")
    for st in ["Granted", "EC Granted", "ToR Granted", "Delisted", "Rejected", "Withdrawn", "Closed", "Lapsed", "Returned",
               "Under process", "", None]:
        assert lib.bucket(st) == ec.bucket(st), st


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="build_ec_library.bucket() says it uses 'the same buckets as scripts/refresh_ec.py' but also "
                          "maps 'deleted' to delisted, whereas refresh_ec.bucket('Deleted') is in_process")
def test_bucket_agrees_with_refresh_ec_on_deleted():
    assert lib.bucket("Deleted") == load("refresh_ec").bucket("Deleted")


def test_op_and_opn(tmp_path):
    assert lib.op({"other_property": op("a")}) == {"Activity": "a"}
    assert lib.op({}) == {} and lib.op({"other_property": "{bad"}) == {}
    g, plain = tmp_path / "x.json.gz", tmp_path / "x.json"
    with gzip.open(g, "wt") as f:
        f.write("gz")
    plain.write_text("plain")
    assert lib.opn(str(g)).read() == "gz" and lib.opn(str(plain)).read() == "plain"


def test_p2_rows_parse_activity_and_normalise(sources):
    rows = list(lib.p2_rows(sources[0]))
    assert len(rows) == 3
    a, b, c = rows
    assert a["state"] == "GOA" and a["activity_code"] == "5(f)" and a["activity_label"] == "Synthetic organic chemicals"
    assert a["submitted_at"] == "2024-03-05" and a["status_bucket"] == "granted" and a["proposal_for"] == "Fresh"
    assert b["activity_code"] is None and b["submitted_at"] is None and b["status_bucket"] == "dead"
    assert c["proposal_no"] is None and c["status_bucket"] == "tor_granted" and c["activity_code"] == "1(a)"


def test_dash_rows_dedup_on_proposal_no_keeping_the_last(sources):
    rows = {r["proposal_no"]: r for r in lib.dash_rows(sources[1])}
    assert set(rows) == {"D1", "P1"}
    d1 = rows["D1"]
    assert d1["project_name"] == "Biodiesel Hub" and d1["company"] == "Second" and d1["state"] == "GOA"
    assert d1["submitted_at"] == "2025-01-02" and d1["granted_at"] == "2025-02-03" and d1["accepted_at"] is None
    assert rows["P1"]["submitted_at"] == "2025-05-06"                     # falls back to start_date


def test_legacy_rows_form_state_and_sector_code(sources):
    rows = list(lib.legacy_rows(sources[2]))
    by = {r["file_no"]: r for r in rows}
    assert by["F1"]["form"] == "post_2014" and by["F1"]["state_code"] == "GA" and by["F1"]["sector_code"] == "IND2"
    assert by["F3"]["form"] == "pre_2014" and by["F3"]["state_code"] == "KL"
    assert by["F2"]["sector_code"] is None and by["F2"]["status_bucket"] == "granted"


def test_load_writes_ndjson_and_creates_table(tmp_path):
    con = duckdb.connect()
    n = lib.load(con, "t", iter([{"a": 1, "b": "x"}, {"a": 2, "b": None}]), str(tmp_path))
    assert n == 2 and con.execute("select count(*), sum(a) from t").fetchone() == (2, 3)
    assert lib.load(con, "empty", iter([]), str(tmp_path)) == 0
    assert con.execute("select count(*) from information_schema.tables where table_name='empty'").fetchone()[0] == 0


@pytest.fixture
def built(tmp_path, sources, monkeypatch, capsys):
    out = tmp_path / "lib"
    monkeypatch.setattr(lib, "LIB", str(out))
    monkeypatch.setattr("sys.argv", ["b", "--p2", sources[0], "--dashboard", sources[1], "--legacy", sources[2]])
    lib.main()
    con = duckdb.connect(str(out / "ec_register.duckdb"), read_only=True)
    yield con, out, capsys.readouterr().out
    con.close()


def test_main_builds_tables_parquet_and_reports_counts(built):
    con, out, printed = built
    assert sorted(f for f in os.listdir(out) if f.endswith(".parquet")) == ["ec_dashboard.parquet", "ec_legacy.parquet", "ec_p2.parquet", "sources.parquet"]
    srcs = dict(con.execute("select table_name, rows from sources").fetchall())
    assert srcs == {"ec_p2": 3, "ec_dashboard": 2, "ec_legacy": 3}
    assert "ec_unified" in printed and "ec_search test" in printed


def test_unified_view_prefers_p2_then_dashboard_then_legacy(built):
    con, _, _ = built
    rows = {r[0]: r for r in con.execute("select proposal_no, project_name, source, state from ec_unified").fetchall()}
    assert rows["P1"][2] == "p2" and rows["P1"][1] == "Bio Diesel Plant"       # also in dashboard, p2 wins
    assert rows["D1"][2] == "dashboard" and rows["P2"][2] == "p2"
    assert rows["IA/GA/IND2/123/2012"][2] == "legacy_post_2014" and rows["IA/KL/MIN/9/2010"][2] == "legacy_pre_2014"
    assert None not in rows                                                     # rows without a proposal number are excluded


def test_ec_search_regex_case_state_filter_and_order(built):
    con, _, _ = built
    names = [r[0] for r in con.execute("select project_name from ec_search('bio[\\s-]?diesel')").fetchall()]
    assert set(names) == {"Bio Diesel Plant", "Biodiesel Hub", "Legacy Bio-diesel"}   # case-insensitive, optional separator
    goa = [r[0] for r in con.execute("select project_name from ec_search('bio[\\s-]?diesel', 'goa')").fetchall()]
    assert set(goa) == {"Bio Diesel Plant", "Biodiesel Hub"}                     # state filter is case-insensitive
    ordered = [r[0] for r in con.execute("select project_name from ec_search('bio[\\s-]?diesel')").fetchall()]
    assert ordered[0] == "Biodiesel Hub" and ordered[-1] == "Legacy Bio-diesel"  # newest first, undated last
    assert con.execute("select count(*) from ec_search('acme fuels')").fetchone()[0] == 1   # company names are searched too


def test_main_with_no_sources_creates_empty_tables(tmp_path, monkeypatch, capsys):
    out = tmp_path / "lib"
    monkeypatch.setattr(lib, "LIB", str(out))
    monkeypatch.setattr("sys.argv", ["b"])
    lib.main()
    con = duckdb.connect(str(out / "ec_register.duckdb"), read_only=True)
    assert con.execute("select count(*) from ec_unified").fetchone()[0] == 0
    assert con.execute("select count(*) from sources").fetchone()[0] == 0
    con.close()


def test_main_rebuilds_over_an_existing_database_and_copies_shared(tmp_path, sources, monkeypatch):
    out, shared = tmp_path / "lib", tmp_path / "shared"
    out.mkdir()
    (out / "SOURCES.md").write_text("doc")
    (out / "ec_register.duckdb").write_text("stale file that is not a database")
    monkeypatch.setattr(lib, "LIB", str(out))
    monkeypatch.setattr("sys.argv", ["b", "--p2", sources[0], "--shared", str(shared)])
    lib.main()
    assert sorted(os.listdir(shared)) == ["SOURCES.md", "ec_dashboard.parquet", "ec_legacy.parquet", "ec_p2.parquet",
                                          "ec_register.duckdb", "sources.parquet"]
    con = duckdb.connect(str(shared / "ec_register.duckdb"), read_only=True)
    assert con.execute("select count(*) from ec_p2").fetchone()[0] == 3
    con.close()
