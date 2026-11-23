"""The network/CLI edge of refresh_ec.py and refresh_other_clearances.py: curl is faked, argv is set,
and build() is captured, so nothing is fetched and no repo data file is rewritten."""
import json
import subprocess

import pytest
from conftest import load

ec = load("refresh_ec")
oc = load("refresh_other_clearances")


class Out:
    def __init__(self, stdout):
        self.stdout = stdout


@pytest.fixture
def curl(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output=None, text=None, timeout=None):
        calls.append({"cmd": cmd, "timeout": timeout, "capture_output": capture_output, "text": text})
        return Out(fake_run.stdout)
    fake_run.stdout = "{}"
    monkeypatch.setattr(subprocess, "run", fake_run)
    return fake_run, calls


# ------------------------------------------------------------------ refresh_ec
def test_ec_fetch_returns_parsed_json_and_uses_curl_with_timeouts(curl):
    fake, calls = curl
    fake.stdout = json.dumps({"data": [1, 2]})
    assert ec.fetch() == {"data": [1, 2]}
    c = calls[0]
    assert c["cmd"][:4] == ["curl", "-s", "-m", "300"] and c["cmd"][-1] == ec.API and c["timeout"] == 320
    assert "majorClearanceType=1" in ec.API


@pytest.mark.parametrize("body", ["", "<html>404</html>", "Not Found"])
def test_ec_fetch_exits_with_a_pointer_when_the_endpoint_is_gone(curl, body):
    fake, _ = curl
    fake.stdout = body
    with pytest.raises(SystemExit) as e:
        ec.fetch()
    assert "--from FILE" in str(e.value) and "build_ec_library.py" in str(e.value)


def test_ec_main_from_dump_skips_the_network(tmp_path, monkeypatch, curl):
    dump = tmp_path / "dump.json"
    dump.write_text(json.dumps({"data": [{"x": 1}]}))
    seen = {}
    monkeypatch.setattr(ec, "build", lambda data: seen.setdefault("data", data))
    monkeypatch.setattr("sys.argv", ["refresh_ec.py", "--from", str(dump)])
    ec.main()
    assert seen["data"] == {"data": [{"x": 1}]} and curl[1] == []


def test_ec_main_without_args_fetches_then_builds(monkeypatch, curl):
    fake, calls = curl
    fake.stdout = json.dumps({"data": []})
    seen = {}
    monkeypatch.setattr(ec, "build", lambda data: seen.setdefault("data", data))
    monkeypatch.setattr("sys.argv", ["refresh_ec.py"])
    ec.main()
    assert seen["data"] == {"data": []} and len(calls) == 1


# ------------------------------------------------------------------ refresh_other_clearances
def test_oc_fetch_formats_the_type_into_the_url_and_unwraps_data(curl):
    fake, calls = curl
    fake.stdout = json.dumps({"data": [{"a": 1}]})
    assert oc.fetch(3) == [{"a": 1}]
    assert "majorClearanceType=3" in calls[0]["cmd"][-1] and calls[0]["timeout"] == 320


def test_oc_fetch_raises_on_non_json(curl):
    fake, _ = curl
    fake.stdout = "<html>"
    with pytest.raises(ValueError):
        oc.fetch(2)


def test_oc_load_dir_reads_the_per_type_file(tmp_path):
    (tmp_path / "parivesh_type4.json").write_text(json.dumps({"data": [{"s": "x"}]}))
    assert oc.load_dir(4, str(tmp_path)) == [{"s": "x"}]
    with pytest.raises(FileNotFoundError):
        oc.load_dir(2, str(tmp_path))


def test_oc_main_from_dir_reads_each_requested_type(tmp_path, monkeypatch, curl):
    for t in (2, 3, 4):
        (tmp_path / f"parivesh_type{t}.json").write_text(json.dumps({"data": [{"t": t}]}))
    got = {}

    def fake_build(get_rows):
        for t in (2, 3, 4):
            got[t] = get_rows(t)
    monkeypatch.setattr(oc, "build", fake_build)
    monkeypatch.setattr("sys.argv", ["refresh_other_clearances.py", "--from-dir", str(tmp_path)])
    oc.main()
    assert got == {2: [{"t": 2}], 3: [{"t": 3}], 4: [{"t": 4}]} and curl[1] == []


def test_oc_main_default_uses_the_network_fetcher(monkeypatch):
    seen = {}
    monkeypatch.setattr(oc, "build", lambda get: seen.setdefault("get", get))
    monkeypatch.setattr("sys.argv", ["refresh_other_clearances.py"])
    oc.main()
    assert seen["get"] is oc.fetch
