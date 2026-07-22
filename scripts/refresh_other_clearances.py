#!/usr/bin/env python3
"""Refresh the Forest / Wildlife / CRZ clearance registers from PARIVESH 2.0.

The SAME open, unauthenticated API that serves Environmental Clearances
(majorClearanceType=1, handled by refresh_ec.py) also serves the other three
central green clearances under different type codes:

    majorClearanceType=2  Forest Clearance      (FC)  ~29k proposals, ~34 MB
    majorClearanceType=3  Wildlife Clearance     (WLC) ~5k proposals
    majorClearanceType=4  CRZ Clearance          (CRZ) ~2k proposals

One GET per type returns the whole national register (pageSize/pageNo are
ignored by the server, so the payload is the full set regardless).

The prize field is Forest Clearance's `forest_area` (hectares) -- populated on
92% of proposals -- which is a direct land-QUANTUM measure the EC register
lacks. Forest diversion is a second land-creation channel alongside the
industrial land bank: mining, linear infra and hydro convert forest to
non-forest use here. `clearanceType` gives the FORM (Form-A = fresh diversion;
Form-B/D/E/F = renewal/transfer/re-diversion on already-diverted land), enabling
the forest analogue of the EC fresh-vs-reuse split.

    python3 scripts/refresh_other_clearances.py                 # fetch + rebuild
    python3 scripts/refresh_other_clearances.py --from-dir DIR  # rebuild from
        saved parivesh_type{2,3,4}.json dumps in DIR

Honesty notes carried into the output:
 - Grant rate = granted / (granted + in_process); 'dead' (rejected/withdrawn/
   returned) and 'delisted' (PARIVESH auto-cleanup) are excluded from the
   denominator, matching the EC methodology.
 - FC 'granted' = "Final Diversion Order Issued" or "Stage-II Accorded" (final
   approval). Stage-I (in-principle) is NOT counted as granted.
 - The forest_area PIPELINE total mixes all statuses (incl. delisted) and is
   skewed by a single ~74,000-ha outlier; the GRANTED forest-area total is the
   trustworthy "forest actually diverted" figure and is reported separately.
"""
import argparse, collections, datetime, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = ("https://parivesh.nic.in/parivesh_api/trackYourProposal/advanceSearchData"
       "?majorClearanceType={t}&state=&proposalStatus=&pageNo=0&pageSize=200000")
TYPES = {2: ("FC", "Forest Clearance"), 3: ("WLC", "Wildlife Clearance"), 4: ("CRZ", "CRZ Clearance")}
HA_TO_ACRE = 2.47105
LIVE = {"granted", "in_process"}


def num(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None


def bucket(status, kind):
    """Per-type status bucketing -- each clearance has its own status vocabulary."""
    s = (status or "").lower()
    if "delist" in s:
        return "delisted"
    if s == "removed":
        return "dead"
    if kind == "FC":
        if "final diversion order issued" in s or "stage-ii accorded" in s:
            return "granted"
        if any(x in s for x in ("reject", "return", "closed", "withdraw")):
            return "dead"
        return "in_process"   # incl. Stage-I in-principle, all "Pending at ..." and EDS states
    if kind == "WLC":
        if ("recommend" in s and "not" not in s) or "dispos" in s:
            return "granted"   # NBWL/SBWL recommendation is the approval instrument
        if any(x in s for x in ("reject", "return", "closed", "withdraw")):
            return "dead"
        return "in_process"
    # CRZ
    if "grant" in s:
        return "granted"
    if any(x in s for x in ("reject", "return", "closed", "withdraw")):
        return "dead"
    return "in_process"


def fetch(t):
    print(f"fetching PARIVESH majorClearanceType={t} ...", file=sys.stderr)
    out = subprocess.run(["curl", "-s", "-m", "300", API.format(t=t)],
                         capture_output=True, text=True, timeout=320)
    return json.loads(out.stdout)["data"]


def load_dir(t, d):
    return json.load(open(os.path.join(d, f"parivesh_type{t}.json")))["data"]


def build(get_rows):
    out = {"built": datetime.date.today().isoformat(),
           "source": ("PARIVESH 2.0 advanceSearchData, majorClearanceType 2=Forest 3=Wildlife 4=CRZ "
                      "(full national register)"),
           "note": ("Companion to the Environmental Clearance analysis (majorClearanceType=1). Same open "
                    "API, same pipeline-snapshot semantics -- proposals span 2022 to the fetch date, "
                    "status is as-of-fetch."),
           "method": ("Grant rate = granted / (granted + in_process); 'dead' and 'delisted' excluded from "
                      "the denominator. FC 'granted' = Final Diversion Order Issued or Stage-II Accorded."),
           "clearances": {}}
    for t, (kind, label) in TYPES.items():
        rows = get_rows(t)
        funnel = collections.Counter()
        by_state = collections.defaultdict(collections.Counter)
        forest_state = collections.defaultdict(lambda: collections.defaultdict(float))
        forms, ua = collections.Counter(), collections.Counter()
        fa_total = fa_granted = 0.0
        for r in rows:
            b = bucket(r.get("proposalStatus"), kind)
            funnel[b] += 1
            st = (r.get("state") or "UNSPECIFIED").strip().upper()
            by_state[st][b] += 1
            if kind == "FC":
                a = num(r.get("forest_area")) or 0.0
                if a > 0:
                    fa_total += a
                    forest_state[st]["all"] += a
                    if b == "granted":
                        fa_granted += a
                        forest_state[st]["granted"] += a
                forms[(r.get("clearanceType") or "?").strip()[:38]] += 1
                ua[(r.get("nameOfUserAgency") or "?").strip()[:40]] += 1
        live = sum(funnel[k] for k in LIVE)
        rec = {"code": kind, "label": label, "total": len(rows), "n_states": len(by_state),
               "funnel": dict(funnel),
               "grant_rate_pct_of_decided": round(funnel["granted"] / live * 100, 1) if live else None,
               "top_states": [{"state": s.title(), "total": sum(c.values()), "granted": c["granted"],
                               "pending": c["in_process"]}
                              for s, c in sorted(by_state.items(), key=lambda kv: -sum(kv[1].values()))[:10]]}
        if kind == "FC":
            fresh = sum(n for f, n in forms.items() if f.startswith("Form-A"))
            rediv = sum(n for f, n in forms.items() if f.startswith("Form-E"))
            renew = sum(n for f, n in forms.items() if f.startswith(("Form-B", "Form-D")))
            transfer = sum(n for f, n in forms.items() if f.startswith("Form-F"))
            rec["forest_area_ha"] = {
                "pipeline_total": round(fa_total), "granted": round(fa_granted),
                "acres_pipeline": round(fa_total * HA_TO_ACRE), "acres_granted": round(fa_granted * HA_TO_ACRE),
                "caveat": ("pipeline_total mixes all statuses incl. delisted and is skewed by a single "
                           "~74,000-ha outlier; 'granted' is the trustworthy forest-actually-diverted figure")}
            rec["forest_area_by_state"] = [
                {"state": s.title(), "pipeline_ha": round(a["all"]), "granted_ha": round(a["granted"]),
                 "granted_acres": round(a["granted"] * HA_TO_ACRE)}
                for s, a in sorted(forest_state.items(), key=lambda kv: -kv[1]["all"])[:12]]
            rec["by_form_type"] = {
                "fresh_diversion_FormA": fresh, "re_diversion_FormE": rediv,
                "renewal_FormBD": renew, "transfer_FormF": transfer,
                "reading": ("Form-A is a FRESH diversion of forest land; Form-B/D/E/F are renewals, transfers "
                            "and re-diversions on already-diverted land -- the forest analogue of the EC "
                            "fresh-vs-reuse split.")}
            rec["top_user_agencies"] = [{"agency": a, "proposals": n}
                                        for a, n in ua.most_common(9) if a != "?"][:8]
        out["clearances"][kind] = rec
        print(f"{kind}: {len(rows):,} proposals | grant% {rec['grant_rate_pct_of_decided']} | "
              f"{rec['n_states']} states"
              + (f" | forest granted {rec['forest_area_ha']['granted']:,} ha "
                 f"({rec['forest_area_ha']['acres_granted']:,} ac)" if kind == "FC" else ""))
    json.dump(out, open(os.path.join(ROOT, "data/parivesh_other_clearances.json"), "w"), indent=1)
    print("wrote data/parivesh_other_clearances.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-dir", dest="d", help="rebuild from saved parivesh_type{2,3,4}.json in DIR")
    args = ap.parse_args()
    get = (lambda t: load_dir(t, args.d)) if args.d else fetch
    build(get)


if __name__ == "__main__":
    main()
