# EC library: sources, coverage and caveats

Built by `scripts/build_ec_library.py` into `ec_register.duckdb` (gitignored, rebuilt on demand) and
the tracked `*.parquet` files beside this note. Query with DuckDB, for example:

```bash
duckdb data/library/ec_register.duckdb "select * from ec_search('biodiesel|sustainable aviation') limit 20"
duckdb -c "select status_bucket, count(*) from 'data/library/ec_p2.parquet' group by 1"
```

| Table | Source | Coverage | Status (checked 2026-11-15) |
|---|---|---|---|
| `ec_p2` | `parivesh.nic.in/parivesh_api/trackYourProposal/advanceSearchData` full dump (snapshot 2026-10-07) | central + state (SEIAA), PARIVESH 2.0, 2022 onward, 119,051 proposals | **Endpoint now 404.** Only the saved dump exists. Needed for state-level (B2) data. |
| `ec_dashboard` | `parivesh.nic.in/admin_api/dashboard/getProposals` (anonymous MIS drill-down, snapshot 2026-11-15) | **central (MoEFCC) only**, 2023 onward, 7,973 proposals. `is_state=true` returns nothing; the status filter is ignored; the API ignores page/size and returns the full window. | Open, no auth. Same route used by `digital-twin-for-ipa/scripts/parivesh_fisheries_requery.py`. |
| `ec_legacy` | `environmentclearance.nic.in/searchproposal.aspx` (two forms: received up to 3 Jul 2014, and from 4 Jul 2014) | pre-2022 register, crawled state by state with the prefix `IA/<state>/`. Fields: proposal no., file no., project, company, status only (no dates, category or sector). | Open, no captcha; slow (~12 s/page, 50 rows/page). |

Objects: `ec_unified` (one row per proposal number, priority p2 > dashboard > legacy) and the topic-neutral
macro `ec_search(pattern, st := null)` (case-insensitive regex over project and company names, optional state).
Nothing in the library is tied to one sector. Other projects attach it read-only:

```sql
attach '~/data/ec_register/ec_register.duckdb' as ec (read_only);
use ec;                      -- macros resolve names in the current catalog
select * from ec_search('solar|wind', 'RAJASTHAN');
```

Caveats
- `ec_search` matches words in project or company names, so a company named after a topic (e.g. "Orissa Biodiesel Jatropha"
  filing a quarry) will match. Check each row's proposal number and sector.
- Legacy crawl misses proposals whose numbers do not contain `IA/<state>/`.
- Proposal numbers can repeat across filings (amendments, transfers); `ec_unified` keeps one row per number.
- The legacy site's certificate chain is incomplete, so Python's `urllib` fails verification and `curl` works; the crawler uses `curl`.
- Fetch politely (one request at a time with a delay); stop on any captcha or login wall.
