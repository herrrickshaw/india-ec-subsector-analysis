# India Environmental Clearances — state × sub-sector

<!-- how-to-use-with-ai -->
> **New here?** See [How to use this repo with AI (Claude, Gemini, ChatGPT)](HOW_TO_USE_WITH_AI.md) — clone it, paste it into an AI tool, and ask in plain English.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/herrrickshaw/india-ec-subsector-analysis/blob/main/notebooks/colab_test.ipynb)

The full national Environmental Clearance (EC) register from PARIVESH 2.0 — 113,970 proposals — pivoted to
answer one question the government's own dashboards do not: which state leads each industrial sub-sector,
and how do clearance rates differ by activity? A companion pass covers the other three central green
clearances (Forest, Wildlife, CRZ). Outputs are small JSON/CSV data files in `data/` and two static HTML
pages in `docs/`, published at
**[herrrickshaw.github.io/india-ec-subsector-analysis](https://herrrickshaw.github.io/india-ec-subsector-analysis/)**.

> Status: maintained snapshot. Data is a pipeline snapshot of PARIVESH 2.0 as of 2026-07-22 (not a time
> series); the register is public government data, re-published here as aggregates only.

## What it does
- Fetches the entire EC register in one unauthenticated GET from the PARIVESH 2.0 open API (`scripts/refresh_ec.py`).
- Buckets each proposal's status into granted · ToR-granted · in-process · dead · delisted, and parses the
  EIA-schedule Activity code (the sub-sector, e.g. `1(a) Mining of minerals`) from `other_property`.
- Builds a state × activity × status matrix (2,055 cells, 36 states/UTs), a per-sub-sector grant rate with
  top-4 state leaders (22 sub-sectors with ≥50 proposals), and a flat CSV pivot.
- Renders `docs/index.html` with a client-side repivot: pick any sub-sector and see the full state ranking.
- Repeats the funnel for Forest (type 2), Wildlife (type 3) and CRZ (type 4) clearances, including forest
  land diverted in hectares (`scripts/refresh_other_clearances.py` → `docs/other_clearances.html`).

## Quick start
```bash
git clone https://github.com/herrrickshaw/india-ec-subsector-analysis.git
cd india-ec-subsector-analysis
python3 -m venv .venv && source .venv/bin/activate
pip install pytest ruff              # standard library only at runtime; curl must be on PATH
python3 scripts/refresh_ec.py        # fetch (~126 MB) + rebuild the three EC data files
python3 scripts/build_page.py        # regenerate docs/index.html
```

Rebuild from a saved dump instead of fetching, or write somewhere other than `data/`/`docs/`:

```bash
python3 scripts/refresh_ec.py --from dump.json --data-dir /tmp/out
python3 scripts/build_page.py --data-dir /tmp/out --out /tmp/out/index.html
python3 scripts/refresh_other_clearances.py --from-dir DIR   # DIR holds parivesh_type{2,3,4}.json
python3 scripts/build_other_clearances.py
```

## How it works

| Stage | Module | Output |
|---|---|---|
| fetch (one GET per `majorClearanceType`, via `curl`) | `ec_analysis/parivesh.py` | JSON envelope `{"data": [...]}` |
| clean + aggregate EC rows (pure functions) | `ec_analysis/ec.py` | matrix doc, analysis doc, CSV rows |
| clean + aggregate FC/WLC/CRZ rows (pure functions) | `ec_analysis/other_clearances.py` | report doc |
| constants, paths, endpoint | `ec_analysis/config.py` | — |
| CLI wrappers | `scripts/refresh_*.py` | `data/*.json`, `data/*.csv` |
| render static pages (pure `render()` + file write) | `scripts/build_page.py`, `scripts/build_other_clearances.py` | `docs/*.html` |

Design points:
- **Sub-sector = the EIA-schedule Activity code** on each proposal. 8,037 proposals carry no parseable code —
  excluded from the sub-sector view, kept in state totals.
- **Grant rate excludes delisted proposals** from the denominator (PARIVESH's auto-cleanup of inactive
  applications, ~22% of the register), so the rate reflects live decisions. EC: granted ÷ (granted +
  ToR-granted + in-process). FC/WLC/CRZ: granted ÷ (granted + in-process). The delisted count is shown, not hidden.
- **FC "granted"** = "Final Diversion Order Issued" or "Stage-II Accorded"; Stage-I in-principle is not counted.
- Aggregation never touches the network or the repo's `data/` directory, so it is testable on a few synthetic rows.

## Headline patterns (snapshot 2026-07-22)

| | |
|---|---|
| **Mining dominates** | `1(a)` alone is 78,867 proposals — 69% of the register. Rajasthan holds 38% of all mining grants. |
| **States specialise by sub-sector** | Gujarat owns chemicals (`5(f)` 56% of grants, pesticides `5(b)` 68%, oil & gas, mineral beneficiation); Chhattisgarh leads metallurgy and thermal power; Maharashtra leads construction and townships; Odisha leads distilleries. |
| **Grant rates swing by activity** | Construction `8(a)` clears at 81% and mining at 70%, but townships `8(b)` only 38% and river-valley `1(c)` just 22%. |
| **Rajasthan is the volume leader** | 35,029 proposals — 2.6× the next state (Maharashtra 13,542) — almost entirely minor-mineral mining. |

The other three green gates:

| Clearance | Type | Proposals | Grant rate (of decided) | Note |
|---|---|--:|--:|---|
| Environmental (EC) | 1 | 113,970 | 88.7% | the register analysed above |
| Forest (FC) | 2 | 28,999 | 42.0% | carries `forest_area` in hectares on 92% of proposals |
| Wildlife (WLC) | 3 | 4,919 | 10.7% | the real bottleneck — 88% "Pending at Proponent" |
| CRZ | 4 | 2,264 | 31.3% | coastal, 17 states/UTs |

Forest land with final diversion orders granted: 49,641 ha (122,666 acres) across 6,134 approved proposals,
concentrated in Madhya Pradesh (21,146 ha), Chhattisgarh (8,061) and Assam (7,746). The forest-area *pipeline*
total (~1.05 million ha) mixes all statuses and is skewed by one ~74,000-ha outlier — the *granted* figure is
the reliable one. 88% of FC proposals are fresh Form-A diversions; Form-B/D/E/F are renewals, transfers and
re-diversions on already-diverted land.

**A proposal is not a project.** Classifying the register by "Proposal For": fresh 56,369 (49%) · re-use of
already-cleared land 38,624 (34%: re-appraisal 24,928, transfer 8,723, expansion 4,973) · admin 6,257 (5%) ·
unclassified 12,720 (11%). Minor-mineral re-appraisals alone are 22% of the register, so mining's dominance is
partly a churn artefact of short-lease re-clearance (`data/ec_fresh_vs_reuse.json`).

**IEM vs EC by activity.** For the heavy-manufacturing sliver where both instruments apply, CY2023 EC filings
outnumber DPIIT IEM Part-A filings 1,817 : 421 (4.3×; metallurgy 7.6×, organic chemicals 4.8×, pulp & paper the
lone inversion at 0.2×) — consistent with IEM under-measuring investment
(`data/iem_ec_activity_comparison.json`, `data/iem_sector_counts_sep2024.json`; DPIIT IEM Statistics Report,
Sep-2024, Annexure-3; the 39-category DIPP/SIA scheme maps many-to-many onto EIA codes, as documented in the JSON).

## Repository layout
| Path | Purpose |
|---|---|
| `ec_analysis/` | Library: `config.py` (paths, endpoint, constants), `parivesh.py` (fetch / load dump), `ec.py` (EC pipeline), `other_clearances.py` (FC/WLC/CRZ pipeline) |
| `scripts/` | CLI entry points: `refresh_ec.py`, `build_page.py`, `refresh_other_clearances.py`, `build_other_clearances.py` (`_bootstrap.py` makes the package importable without installing) |
| `data/` | Tracked outputs: `ec_state_subsector_matrix.json`, `ec_subsector_analysis.json`, `ec_state_subsector.csv`, `parivesh_other_clearances.json`; plus `ec_funnel.json`, `ec_fresh_vs_reuse.json`, `iem_*.json` (built 2026-07-22 by one-off analyses whose scripts are not in this repo) |
| `docs/` | GitHub Pages: `index.html`, `other_clearances.html` (generated), `funnel.html` (hand-built from `ec_funnel.json`) |
| `tests/` | pytest suite; `tests/fixtures/` holds synthetic PARIVESH dumps and the pre-refactor outputs they must reproduce |
| `notebooks/colab_test.ipynb` | Runs the four scripts end to end in Colab |
| `graphify-out/` | Knowledge-graph export of the repo (generated) |

## Data sources
| Source | What is taken | Access route | Licence / caveat |
|---|---|---|---|
| PARIVESH 2.0 (MoEFCC) | Full proposal register per clearance type: state, status, activity code, forest area, form type | `https://parivesh.nic.in/parivesh_api/trackYourProposal/advanceSearchData?majorClearanceType=<1..4>&state=&proposalStatus=&pageNo=0&pageSize=200000` — open JSON API, no key, no CAPTCHA, no pagination (pageNo/pageSize ignored) | Public government data; status is as-of-fetch; corrections in the register are displayed, never silent |
| DPIIT IEM Statistics Report (Sep-2024, Annexure-3) | IEM Part-A counts by industry for the IEM-vs-EC comparison | manual extraction into `data/iem_sector_counts_sep2024.json` | 39-category industry scheme, mapped many-to-many onto EIA codes |

## Configuration
No environment variables and no secrets. Everything is a named constant in `ec_analysis/config.py`
(endpoint template, curl timeouts 300 s, min sub-sector size 50, top-4 state leaders, ha→acre 2.47105).
Output locations default to `data/` and `docs/` and can be overridden per run with `--data-dir` / `--out`.

## Testing
```bash
pytest -q          # 54 tests, offline: unit tests on tiny synthetic rows + golden-file characterisation tests
ruff check .
```

## Limitations and known issues
- Pipeline snapshot, not a time series: proposals span 2022 to the fetch date and status is as-of-fetch.
- Counts are clearance *events*, not distinct sites (see fresh-vs-reuse above).
- `data/ec_funnel.json`, `data/ec_fresh_vs_reuse.json` and the two `iem_*.json` files, and `docs/funnel.html`,
  cannot be regenerated from this repo — their one-off scripts were not committed.
- The fetch shells out to `curl` and reads the full ~126 MB EC response into memory.
- The WLC "granted" bucket treats any status containing "recommend" (without "not") or "dispos" as approval.

## Related repositories
- [india-trade-sector-policy-recommendations](https://github.com/herrrickshaw/india-trade-sector-policy-recommendations)
  — uses the state EC pipeline as a leading indicator of industrial implementation.

## Licence
No licence file yet — all rights reserved.
