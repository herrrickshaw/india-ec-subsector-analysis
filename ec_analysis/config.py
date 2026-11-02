"""Paths, endpoints and named constants shared by the pipelines."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

# PARIVESH 2.0 open API: one unauthenticated GET returns the whole national
# register for a clearance type (pageNo/pageSize are ignored by the server).
API_URL = (
    "https://parivesh.nic.in/parivesh_api/trackYourProposal/advanceSearchData"
    "?majorClearanceType={clearance_type}&state=&proposalStatus=&pageNo=0&pageSize=200000"
)
CURL_TIMEOUT_S = 300          # curl -m
SUBPROCESS_TIMEOUT_S = 320    # hard cap on the curl subprocess

# majorClearanceType codes
EC_TYPE = 1
OTHER_TYPES = {2: ("FC", "Forest Clearance"), 3: ("WLC", "Wildlife Clearance"), 4: ("CRZ", "CRZ Clearance")}

# --- Environmental Clearance (EC) pipeline ---------------------------------
EC_MATRIX_FILE = "ec_state_subsector_matrix.json"
EC_ANALYSIS_FILE = "ec_subsector_analysis.json"
EC_CSV_FILE = "ec_state_subsector.csv"
EC_LIVE_BUCKETS = frozenset({"granted", "tor_granted", "in_process"})
EC_DEAD_KEYWORDS = ("reject", "withdraw", "closed", "lapsed", "returned")
EC_MIN_SUBSECTOR_TOTAL = 50   # sub-sectors with fewer proposals are not analysed
EC_TOP_STATES = 4             # state leaders listed per sub-sector
EC_LABEL_MAX_CHARS = 60
UNCLASSIFIED = "UNCLASSIFIED"
UNSPECIFIED_STATE = "UNSPECIFIED"

# --- Forest / Wildlife / CRZ pipeline ---------------------------------------
OTHER_OUTPUT_FILE = "parivesh_other_clearances.json"
OTHER_LIVE_BUCKETS = frozenset({"granted", "in_process"})
OTHER_DEAD_KEYWORDS = ("reject", "return", "closed", "withdraw")
HA_TO_ACRE = 2.47105
OTHER_TOP_STATES = 10
FOREST_TOP_STATES = 12
FOREST_TOP_AGENCIES = 8
FORM_LABEL_MAX_CHARS = 38
AGENCY_LABEL_MAX_CHARS = 40
