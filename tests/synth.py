"""Tiny synthetic snapshot (same schema as data/*.json) used by the page-builder and summary tests."""
import csv
import json
import os

STATUSES = ("granted", "tor_granted", "in_process", "dead", "delisted")


def matrix():
    cells = [
        ("GOA", "1(a)", "granted", 6), ("GOA", "1(a)", "in_process", 2),
        ("GOA", "5(f)", "granted", 1), ("GOA", "5(f)", "dead", 1),
        ("KERALA", "1(a)", "granted", 3), ("KERALA", "1(a)", "delisted", 4),
        ("KERALA", "5(f)", "tor_granted", 2),
    ]
    return {"built": "2026-01-01", "source": "synthetic", "total_proposals": sum(c[3] for c in cells),
            "n_states": 2, "n_subsectors": 2, "unclassified_activity": 3,
            "activity_labels": {"1(a)": "Mining of minerals", "5(f)": "Synthetic organic chemicals"},
            "matrix": [{"state": s, "activity": a, "status": st, "count": n} for s, a, st, n in cells]}


def analysis(m=None):
    m = m or matrix()
    subs = {}
    for c in m["matrix"]:
        subs.setdefault(c["activity"], dict.fromkeys(STATUSES, 0))[c["status"]] += c["count"]
    out = []
    for act, st in subs.items():
        live = st["granted"] + st["tor_granted"] + st["in_process"] + st["dead"]
        out.append({"activity": act, "label": m["activity_labels"][act], "total": sum(st.values()), **st,
                    "grant_rate_pct": round(st["granted"] / live * 100, 1) if live else None,
                    "top_states": [{"state": "Goa", "granted": st["granted"], "share_pct": 100.0}]})
    states = {}
    for c in m["matrix"]:
        states[c["state"].title()] = states.get(c["state"].title(), 0) + c["count"]
    return {"built": "2026-01-01", "n_subsectors": len(out), "subsector_analysis": out,
            "state_totals": [{"state": k, "total": v} for k, v in sorted(states.items(), key=lambda kv: -kv[1])]}


def other():
    def rec(code, label, funnel, **extra):
        total = sum(funnel.values())
        decided = funnel.get("granted", 0) + funnel.get("dead", 0)
        active = decided + funnel.get("in_process", 0)
        return {"code": code, "label": label, "total": total, "n_states": 2, "funnel": funnel,
                "grant_rate_pct_of_decided": round(funnel.get("granted", 0) / decided * 100, 1) if decided else None,
                "grant_rate_pct_of_active": round(funnel.get("granted", 0) / active * 100, 1) if active else None,
                "top_states": [{"state": "Goa", "n": 1}], **extra}
    fc = rec("FC", "Forest Clearance", {"granted": 6, "in_process": 3, "dead": 1, "delisted": 2},
             forest_area_ha={"pipeline_total": 1000, "granted": 400, "acres_pipeline": 2470, "acres_granted": 988, "caveat": "x"},
             forest_area_by_state=[{"state": "Goa", "granted_ha": 400, "granted_acres": 988, "pipeline_ha": 600}],
             by_form_type={"fresh_diversion_FormA": 8, "re_diversion_FormE": 2, "renewal_FormBD": 1, "transfer_FormF": 1, "reading": "r"},
             top_user_agencies=[{"agency": "PWD", "proposals": 4}])
    return {"built": "2026-01-01", "source": "synthetic", "note": "n", "method": "m",
            "clearances": {"FC": fc, "WLC": rec("WLC", "Wildlife Clearance", {"in_process": 5, "granted": 1}),
                           "CRZ": rec("CRZ", "CRZ Clearance", {"granted": 2, "dead": 2})}}


def write_snapshot(root, m=None, a=None, o=None, csv_total=None):
    d = os.path.join(root, "data")
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(root, "docs"), exist_ok=True)
    m = m or matrix()
    json.dump(m, open(os.path.join(d, "ec_state_subsector_matrix.json"), "w"))
    json.dump(a or analysis(m), open(os.path.join(d, "ec_subsector_analysis.json"), "w"))
    json.dump(o or other(), open(os.path.join(d, "parivesh_other_clearances.json"), "w"))
    with open(os.path.join(d, "ec_state_subsector.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["state", "activity_code", "activity_label", "status", "count"])
        rows = [(c["state"], c["activity"], "", c["status"], c["count"]) for c in m["matrix"]]
        if csv_total is not None:
            rows[0] = rows[0][:4] + (rows[0][4] + csv_total,)
        w.writerows(rows)
    return d
