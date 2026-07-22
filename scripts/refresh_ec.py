#!/usr/bin/env python3
"""Refresh the Environmental Clearance state x sub-sector matrix from PARIVESH 2.0.

PARIVESH 2.0 exposes a fully open, unauthenticated JSON API — no key, no
CAPTCHA, no pagination — that returns the entire national EC proposal register
in a single GET. One call replaces a scraping campaign.

    Endpoint: https://parivesh.nic.in/parivesh_api/trackYourProposal/advanceSearchData
    Params:   majorClearanceType=1  (1 = Environmental Clearance)
              state=  proposalStatus=  pageNo=0  pageSize=200000

Each proposal carries: state, an EIA-schedule Activity code in other_property
(this is the SUB-SECTOR — e.g. "1(a) Mining of minerals", "5(f) Synthetic
organic chemicals"), proposalStatus, category (A/B1/B2), issuing authority.

Output: data/ec_state_subsector_matrix.json (state x activity x status counts),
data/ec_subsector_analysis.json (per-sub-sector grant rate + state leaders),
data/ec_state_subsector.csv (flat pivot). Build docs with build_page.py.

    python3 scripts/refresh_ec.py            # fetch + rebuild
    python3 scripts/refresh_ec.py --from FILE  # rebuild from a saved dump

Status buckets: 'delisted' is PARIVESH's auto-cleanup of inactive applications
(~22% of the register) — excluded from grant-rate denominators, kept in totals
so the exclusion is visible. Grant rate = granted / (granted + tor_granted +
in_process); dead = rejected/withdrawn/closed/lapsed/returned.
"""
import argparse, collections, datetime, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = ("https://parivesh.nic.in/parivesh_api/trackYourProposal/advanceSearchData"
       "?majorClearanceType=1&state=&proposalStatus=&pageNo=0&pageSize=200000")
ACT = re.compile(r"^\s*(\d+\([a-z]+\))\s*(.*)")
LIVE = {"granted", "tor_granted", "in_process"}


def bucket(status):
    s = (status or "").lower()
    if "tor" in s and "grant" in s:
        return "tor_granted"
    if "grant" in s:
        return "granted"
    if "delist" in s:
        return "delisted"
    if any(x in s for x in ("reject", "withdraw", "closed", "lapsed", "returned")):
        return "dead"
    return "in_process"


def props(r):
    try:
        return {p["label"]: p["value"] for p in json.loads(r.get("other_property") or "[]")}
    except Exception:
        return {}


def fetch():
    print(f"fetching PARIVESH EC register (~126 MB) ...", file=sys.stderr)
    out = subprocess.run(["curl", "-s", "-m", "300", API], capture_output=True, text=True, timeout=320)
    return json.loads(out.stdout)


def build(data):
    rows = data["data"]
    mat = collections.Counter()
    acts, unclassified = {}, 0
    for r in rows:
        st = str(r.get("state") or "").strip().upper() or "UNSPECIFIED"
        a = str(props(r).get("Activity") or "")
        m = ACT.match(a)
        if m:
            code = m.group(1)
            acts[code] = m.group(2).strip()[:60]
        else:
            code = a.split()[0] if a.strip() else "UNCLASSIFIED"
            unclassified += 1
        mat[(st, code, bucket(r.get("proposalStatus")))] += 1
    today = datetime.date.today().isoformat()
    matrix = {"built": today,
              "source": "PARIVESH 2.0 advanceSearchData?majorClearanceType=1 (Environmental Clearance), full register",
              "total_proposals": len(rows), "n_states": len({k[0] for k in mat}),
              "n_subsectors": len(acts), "unclassified_activity": unclassified,
              "activity_labels": acts,
              "matrix": [{"state": s, "activity": c, "status": b, "count": n}
                         for (s, c, b), n in sorted(mat.items())]}
    json.dump(matrix, open(os.path.join(ROOT, "data/ec_state_subsector_matrix.json"), "w"), indent=0)

    # per-sub-sector analysis
    subsec = collections.defaultdict(collections.Counter)
    sub_state = collections.defaultdict(collections.Counter)
    state_tot = collections.Counter()
    for (s, c, b), n in mat.items():
        subsec[c][b] += n
        state_tot[s] += n
        if b == "granted":
            sub_state[c][s] += n
    analysis = []
    for code, st in sorted(subsec.items(), key=lambda kv: -sum(kv[1].values())):
        tot = sum(st.values())
        if tot < 50 or code in ("UNCLASSIFIED",) or ")" not in code:
            continue
        live = sum(v for k, v in st.items() if k in LIVE)
        gtot = sum(sub_state[code].values()) or 1
        analysis.append({"activity": code, "label": acts.get(code, "?"), "total": tot,
                         "granted": st["granted"], "tor_granted": st["tor_granted"],
                         "in_process": st["in_process"], "dead": st["dead"], "delisted": st["delisted"],
                         "grant_rate_pct": round(st["granted"] / live * 100, 1) if live else None,
                         "top_states": [{"state": s.title(), "granted": n, "share_pct": round(n / gtot * 100, 1)}
                                        for s, n in sub_state[code].most_common(4)]})
    json.dump({"built": today, "n_subsectors": len(analysis), "subsector_analysis": analysis,
               "state_totals": [{"state": s.title(), "total": n} for s, n in state_tot.most_common()]},
              open(os.path.join(ROOT, "data/ec_subsector_analysis.json"), "w"), indent=1)

    import csv
    with open(os.path.join(ROOT, "data/ec_state_subsector.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["state", "activity_code", "activity_label", "status", "count"])
        for c in matrix["matrix"]:
            w.writerow([c["state"], c["activity"], acts.get(c["activity"], ""), c["status"], c["count"]])
    print(f"{len(rows):,} proposals · {matrix['n_states']} states · {matrix['n_subsectors']} sub-sectors "
          f"· {len(analysis)} analysed · {unclassified:,} unclassified")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", help="rebuild from a saved JSON dump instead of fetching")
    args = ap.parse_args()
    data = json.load(open(args.src)) if args.src else fetch()
    build(data)


if __name__ == "__main__":
    main()
