"""The fetch edge is exercised only through an injected fetcher -- never the live API."""
from __future__ import annotations

import json

from ec_analysis import parivesh


def test_fetch_register_formats_url_and_decodes():
    seen = []

    def fake_fetch(url):
        seen.append(url)
        return json.dumps({"data": [{"id": 1}]})

    env = parivesh.fetch_register(4, fetcher=fake_fetch)
    assert env == {"data": [{"id": 1}]}
    assert seen == ["https://parivesh.nic.in/parivesh_api/trackYourProposal/advanceSearchData"
                    "?majorClearanceType=4&state=&proposalStatus=&pageNo=0&pageSize=200000"]


def test_load_dump_roundtrip(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"data": []}))
    assert parivesh.load_dump(p) == {"data": []}
