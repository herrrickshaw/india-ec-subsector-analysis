#!/usr/bin/env python3
"""Build the queryable EC library (DuckDB + Parquet) from every collected source.

Sources (see data/library/SOURCES.md for endpoint status and caveats):
  p2         PARIVESH 2.0 advanceSearchData full dump, central + state, 2022+  (endpoint now 404)
  dashboard  PARIVESH admin_api/dashboard/getProposals, central only, 2023+   (open, anonymous)
  legacy     environmentclearance.nic.in search crawl, pre-2022, per state     (ASP.NET grid)

    python3 scripts/build_ec_library.py \
        --p2 ~/masaladeutsch-archive/cache/parivesh_ec_2026-10-07.json.gz \
        --dashboard ~/masaladeutsch-archive/cache/parivesh_dashboard_2026-11-15.json.gz \
        --legacy ~/masaladeutsch-archive/cache/legacy_ec

Outputs (data/library/):
  ec_register.duckdb   all tables + views (gitignored, rebuilt from the sources)
  *.parquet            one file per table, zstd (tracked, ~no LFS needed)

Query:  duckdb data/library/ec_register.duckdb "select * from ec_search('biodiesel')"
"""
import argparse, glob, gzip, json, os, re, sys, tempfile
import duckdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "data", "library")
ACT = re.compile(r"^\s*(\d+\([a-z]+\))\s*(.*)")


def bucket(status):
    # same buckets as scripts/refresh_ec.py
    s = (status or "").lower()
    if "tor" in s and "grant" in s:
        return "tor_granted"
    if "grant" in s:
        return "granted"
    if "delist" in s or "deleted" in s:
        return "delisted"
    if any(x in s for x in ("reject", "withdraw", "closed", "lapsed", "returned")):
        return "dead"
    return "in_process"


def op(r):
    try:
        return {p["label"]: p["value"] for p in json.loads(r.get("other_property") or "[]")}
    except Exception:
        return {}


def opn(path):
    return gzip.open(path, "rt") if path.endswith(".gz") else open(path)


def p2_rows(path):
    for r in json.load(opn(path))["data"]:
        p = op(r)
        m = ACT.match(str(p.get("Activity") or ""))
        yield {
            "proposal_no": r.get("proposalNo"), "project_name": r.get("projectName"),
            "company": r.get("nameOfUserAgency"), "state": (r.get("state") or "").strip().upper(),
            "status": r.get("proposalStatus"), "status_bucket": bucket(r.get("proposalStatus")),
            "category": r.get("category"), "sector": r.get("sector"),
            "authority": r.get("issuing_authority"),
            "activity_code": m.group(1) if m else None, "activity_label": m.group(2).strip() if m else None,
            "proposal_for": p.get("Proposal For"), "submitted_at": (r.get("dateOfSubmission") or "")[:10] or None,
            "certificate_url": r.get("certificate_url"),
        }


def dash_rows(path):
    seen = {}
    for r in json.load(opn(path))["data"]:
        seen[r["proposal_no"]] = r
    for r in seen.values():
        yield {
            "proposal_no": r.get("proposal_no"), "project_name": r.get("project_name"),
            "company": r.get("name_of_proponent") or r.get("proponent"),
            "state": (r.get("state_name") or "").strip().upper(), "status": r.get("status"),
            "status_bucket": bucket(r.get("status")), "category": r.get("category"),
            "sector": r.get("sector_name"), "activity": r.get("activity_name"),
            "sub_activity": r.get("sub_activity_name"), "district": r.get("district_name"),
            "submitted_at": (r.get("submit_date") or r.get("start_date") or "")[:10] or None,
            "accepted_at": (r.get("accepted_date") or "")[:10] or None,
            "granted_at": (r.get("granted_date") or "")[:10] or None,
        }


def legacy_rows(d):
    for fn in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
        form, st = re.match(r"(C_D|Rpn)_(.+)$", os.path.basename(fn)[:-6]).groups()
        for line in open(fn):
            r = json.loads(line)
            m = re.match(r"IA/([A-Z]+)/([A-Z0-9]+)/", r["proposal_no"] or "")
            yield {"form": "post_2014" if form == "Rpn" else "pre_2014", "state_code": st,
                   "proposal_no": r["proposal_no"], "file_no": r["file_no"], "project_name": r["project"],
                   "company": r["company"], "status": r["status"], "status_bucket": bucket(r["status"]),
                   "sector_code": m.group(2) if m else None}


def load(con, table, rows, tmp):
    fn = os.path.join(tmp, table + ".ndjson")
    n = 0
    with open(fn, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n"); n += 1
    if n:
        con.execute(f"create or replace table {table} as select * from read_json_auto('{fn}', format='newline_delimited', sample_size=-1)")
    return n


VIEWS = """
create or replace view ec_unified as
with u as (
  select proposal_no, project_name, company, state, status, status_bucket, category, sector,
         submitted_at::date as submitted_at, 'p2' as source, 1 as pri from ec_p2
  union all
  select proposal_no, project_name, company, state, status, status_bucket, category, sector,
         try_cast(submitted_at as date), 'dashboard', 2 from ec_dashboard
  union all
  select proposal_no, project_name, company, state_code, status, status_bucket, null, sector_code,
         null, 'legacy_' || form, 3 from ec_legacy
)
select * exclude (pri) from (
  select *, row_number() over (partition by proposal_no order by pri) rn from u where proposal_no is not null
) where rn = 1;

-- topic-neutral keyword search over project and company names, any regex, optional state filter:
--   select * from ec_search('bio[\\s-]?diesel|\\bSAF\\b');  select * from ec_search('solar', 'GUJARAT');
create or replace macro ec_search(pat, st := null) as table
  select * from ec_unified
  where regexp_matches(coalesce(project_name,'') || ' ' || coalesce(company,''), '(?i)' || pat)
    and (st is null or state = upper(st))
  order by submitted_at desc nulls last;
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p2"); ap.add_argument("--dashboard"); ap.add_argument("--legacy")
    ap.add_argument("--shared", help="also copy the built library here so other projects can ATTACH it (e.g. ~/data/ec_register)")
    a = ap.parse_args()
    os.makedirs(LIB, exist_ok=True)
    db = os.path.join(LIB, "ec_register.duckdb")
    if os.path.exists(db):
        os.remove(db)
    con = duckdb.connect(db)
    log = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, src, gen, desc in (
            ("ec_p2", a.p2, p2_rows, "PARIVESH 2.0 advanceSearchData full dump (central+state, 2022+)"),
            ("ec_dashboard", a.dashboard, dash_rows, "PARIVESH admin_api dashboard (central only, 2023+)"),
            ("ec_legacy", a.legacy, legacy_rows, "environmentclearance.nic.in crawl (pre-2022)"),
        ):
            if not src:
                con.execute(f"create table {name} (proposal_no varchar, project_name varchar, company varchar, state varchar, state_code varchar, status varchar, status_bucket varchar, category varchar, sector varchar, sector_code varchar, submitted_at varchar, form varchar)")
                continue
            n = load(con, name, gen(os.path.expanduser(src)), tmp)
            log.append((name, desc, os.path.basename(src.rstrip("/")), n))
    # fill columns the unified view expects but a source may lack
    for t, cols in (("ec_p2", ["category", "sector"]), ("ec_dashboard", ["category", "sector"]),
                    ("ec_legacy", ["state_code", "sector_code", "form"])):
        have = {r[0] for r in con.execute(f"describe {t}").fetchall()}
        for c in cols:
            if c not in have:
                con.execute(f"alter table {t} add column {c} varchar")
    con.execute("create or replace table sources(table_name varchar, description varchar, input varchar, rows bigint, built_on date)")
    for t, d, i, n in log:
        con.execute("insert into sources values (?,?,?,?,current_date)", [t, d, i, n])
    con.execute(VIEWS)
    for t in ("ec_p2", "ec_dashboard", "ec_legacy", "sources"):
        con.execute(f"copy {t} to '{LIB}/{t}.parquet' (format parquet, compression zstd)")
    for t, n in con.execute("select table_name, rows from sources").fetchall():
        print(f"{t:14s} {n:>9,}")
    print("ec_unified    ", con.execute("select count(*) from ec_unified").fetchone()[0])
    print("ec_search test", con.execute("select count(*) from ec_search('biodiesel')").fetchone()[0])
    con.close()
    if a.shared:
        import shutil
        d = os.path.expanduser(a.shared); os.makedirs(d, exist_ok=True)
        for f in glob.glob(LIB + "/*.parquet") + [db, LIB + "/SOURCES.md"]:
            shutil.copy2(f, d)
        print("shared copy ->", d)


if __name__ == "__main__":
    main()
