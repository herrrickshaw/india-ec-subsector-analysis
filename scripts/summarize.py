#!/usr/bin/env python3
"""Headline totals + consistency checks for a PARIVESH data snapshot.

    python3 scripts/summarize.py                  # summarise data/
    python3 scripts/summarize.py DIR              # summarise another snapshot dir
    python3 scripts/summarize.py data --old OLD   # also compare against an older snapshot

Typical refresh workflow:
    cp -r data /tmp/data_old
    python3 scripts/refresh_ec.py && python3 scripts/build_page.py
    python3 scripts/refresh_other_clearances.py && python3 scripts/build_other_clearances.py
    python3 scripts/summarize.py data --old /tmp/data_old

Exits 1 if any consistency check fails, or if (with --old) any headline count
falls by more than --max-drop percent (default 20) — i.e. do not commit.
"""
import argparse, collections, csv, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def summarize(d):
    J = lambda f: json.load(open(os.path.join(d, f)))
    m = J("ec_state_subsector_matrix.json")
    a = J("ec_subsector_analysis.json")
    o = J("parivesh_other_clearances.json")
    status = collections.Counter()
    for r in m["matrix"]:
        status[r["status"]] += r["count"]
    with open(os.path.join(d, "ec_state_subsector.csv")) as f:
        csv_total = sum(int(r["count"]) for r in csv.DictReader(f))
    s = {
        "ec_built": m["built"], "oc_built": o["built"],
        "ec_total_proposals": m["total_proposals"],
        "unclassified_activity": m["unclassified_activity"],
        "n_states": m["n_states"], "n_subsectors": m["n_subsectors"],
        "matrix_cell_total": sum(status.values()),
        "matrix_by_status": dict(status),
        "csv_total": csv_total,
        "state_totals_sum": sum(x["total"] for x in a["state_totals"]),
        "top_states": [(x["state"], x["total"]) for x in
                       sorted(a["state_totals"], key=lambda x: -x["total"])[:5]],
        "top_subsectors": [(x["activity"], x["label"], x["total"], x["grant_rate_pct"]) for x in
                           sorted(a["subsector_analysis"], key=lambda x: -x["total"])[:5]],
        "other_clearances": {k: {"total": v["total"], **v["funnel"],
                                 "grant_rate": v["grant_rate_pct_of_decided"]}
                             for k, v in o["clearances"].items()},
    }
    # The matrix includes proposals with no parseable activity code, so its
    # cell total equals total_proposals (not total_proposals - unclassified).
    s["checks"] = {
        "matrix total == total_proposals": s["matrix_cell_total"] == m["total_proposals"],
        "matrix total == csv total": s["matrix_cell_total"] == csv_total,
        "state_totals sum == total_proposals": s["state_totals_sum"] == m["total_proposals"],
        "unclassified < total_proposals": 0 <= m["unclassified_activity"] < m["total_proposals"],
        "subsector status parts == subsector total": all(
            x["total"] == sum(x[k] for k in ("granted", "tor_granted", "in_process", "dead", "delisted"))
            for x in a["subsector_analysis"]),
        "FC/WL/CRZ funnel parts == total": all(
            v["total"] == sum(v["funnel"].values()) for v in o["clearances"].values()),
    }
    return s


def headlines(s):
    h = {"EC proposals": s["ec_total_proposals"], "matrix total": s["matrix_cell_total"]}
    h.update({f"EC {k}": v for k, v in s["matrix_by_status"].items()})
    for k, v in s["other_clearances"].items():
        h[f"{k} total"] = v["total"]
        h[f"{k} granted"] = v.get("granted", 0)
    return h


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", nargs="?", default=os.path.join(ROOT, "data"))
    ap.add_argument("--old", help="older snapshot dir to compare against")
    ap.add_argument("--max-drop", type=float, default=20.0, help="max allowed %% fall per headline")
    args = ap.parse_args()

    new = summarize(args.dir)
    print(json.dumps(new, indent=1))
    ok = all(new["checks"].values())
    for name, passed in new["checks"].items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}", file=sys.stderr)

    if args.old:
        old = summarize(args.old)
        ho, hn = headlines(old), headlines(new)
        print(f"\n{'headline':<22}{old['ec_built']:>12}{new['ec_built']:>12}{'change':>10}")
        for k in sorted(set(ho) | set(hn)):
            o, n = ho.get(k, 0), hn.get(k, 0)
            pct = (n - o) / o * 100 if o else float("inf") if n else 0.0
            flag = "  <-- DROP" if pct < -args.max_drop else ""
            ok &= not flag
            print(f"{k:<22}{o:>12,}{n:>12,}{pct:>9.1f}%{flag}")

    print("\nOK to commit" if ok else "\nNOT OK — see FAIL / DROP lines above", file=sys.stderr)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
