# India Environmental Clearances — state × sub-sector

The full national **Environmental Clearance (EC) register** from **PARIVESH 2.0**, pivoted to answer one
question the government's own dashboards do not: **which state leads each industrial sub-sector, and how do
clearance rates differ by activity?**

**[→ Interactive analysis (GitHub Pages)](https://herrrickshaw.github.io/india-ec-subsector-analysis/)**

## What's here

- **113,970 EC proposals** across **36 states/UTs** and **22 EIA-schedule sub-sectors** (the "Activity" code
  carried on every proposal — `1(a) Mining of minerals`, `5(f) Synthetic organic chemicals`, `3(a)
  Metallurgical industries`, …).
- Each proposal's **status** bucketed: granted · ToR-granted · in-process · dead (rejected/withdrawn/closed)
  · delisted (PARIVESH auto-cleanup).
- A per-sub-sector **grant rate** and **state-leader** breakdown, and a client-side repivot so you can drop
  any sub-sector and see the full state ranking.

## Headline patterns

| | |
|---|---|
| **Mining dominates** | `1(a)` alone is 78,867 proposals — 69% of the entire register. Rajasthan holds 38% of all mining grants. |
| **States specialise by sub-sector** | Gujarat owns chemicals (`5(f)` 56% of grants, pesticides `5(b)` 68%, oil & gas, mineral beneficiation); Chhattisgarh leads metallurgy and thermal power; Maharashtra leads construction and townships; Odisha leads distilleries. |
| **Grant rates swing by activity** | Construction `8(a)` clears at 81% and mining at 70%, but townships `8(b)` only 38% and river-valley `1(c)` just 22% — the clearance bottleneck is activity-specific, not uniform. |
| **Rajasthan is the volume leader** | 35,029 proposals — 2.6× the next state (Maharashtra 13,542) — almost entirely minor-mineral mining. |

## Data

| File | Contents |
|---|---|
| `data/ec_state_subsector_matrix.json` | state × activity × status counts (2,055 cells) + activity-code labels |
| `data/ec_subsector_analysis.json` | per-sub-sector grant rate + top-4 state leaders; state totals |
| `data/ec_state_subsector.csv` | flat pivot (`state, activity_code, activity_label, status, count`) |

## Refresh

PARIVESH 2.0 exposes a **fully open, unauthenticated JSON API** — no key, no CAPTCHA, no pagination — that
returns the entire national EC register in a single GET. One call replaces a scraping campaign, so this
dataset is trivially refreshable:

```bash
python3 scripts/refresh_ec.py      # fetch (~126 MB) + rebuild all three data files
python3 scripts/build_page.py      # regenerate docs/index.html
```

Endpoint: `parivesh.nic.in/parivesh_api/trackYourProposal/advanceSearchData?majorClearanceType=1`
(`majorClearanceType=1` = Environmental Clearance).

## Method & honesty notes

- **Sub-sector = the EIA-schedule Activity code** on each proposal, parsed from its `other_property` field.
  8,037 proposals carry no parseable activity code — excluded from the sub-sector view, kept in state totals.
- **Grant rate excludes delisted proposals** from the denominator (they are PARIVESH's auto-cleanup of
  inactive applications, ~22% of the register), so the rate reflects live decisions. The delisted count is
  shown, not hidden.
- This is a **pipeline snapshot**, not a time series — proposals span 2022 to the fetch date, and status is
  as-of-fetch. It measures *where and in what* clearances concentrate, not year-on-year flow.
- A companion analysis (state EC pipeline as a leading indicator of industrial implementation) lives in
  [india-trade-sector-policy-recommendations](https://github.com/herrrickshaw/india-trade-sector-policy-recommendations).

Corrections in the underlying register are displayed, never silent.

## Bonus: IEM vs EC by activity (how intent compares to clearance)

A natural question — how does the count of **industrial-investment intentions (IEMs)** compare to the count
of **environmental clearances (ECs)** for the same activities? Two honest constraints shape the answer:

1. **The registers barely overlap.** Of the 14,316 EC proposals filed in CY2023, **62% are mining** — which
   files no IEM at all. Most IEM industries (electricals, machinery, textiles, food processing) sit below
   EIA thresholds and need no EC. The comparison is only meaningful for the heavy/polluting manufacturing
   sliver where *both* instruments apply.
2. **Same-year, same-meaning.** EC submissions in CY2023 are matched against DPIIT IEM **Part A (filed
   intent)** for Jan–Dec 2023 — both represent "intent to set up," so they're the comparable pair.

| EC activity | Industry | IEMs filed (2023) | ECs filed (2023) | EC : IEM |
|---|---|--:|--:|--:|
| 3(a) | Metallurgical industries | 102 | 775 | **7.6×** |
| 5(f) | Organic chemicals + pharma + dyes | 130 | 626 | 4.8× |
| 5(a) | Chemical fertilizers | 12 | 42 | 3.5× |
| 3(b) | Cement | 26 | 83 | 3.2× |
| 5(g) | Distilleries (fermentation) | 119 | 254 | 2.1× |
| 5(j) | Sugar | 16 | 33 | 2.1× |
| 5(i) | Pulp & paper | 16 | 4 | 0.2× |
| | **Heavy-manufacturing overlap** | **421** | **1,817** | **4.3×** |

**The reading**: even in the overlap, EC filings outnumber IEM filings ~4:1. EC is **mandatory** and counts
each project, expansion and lease application; IEM is a **single voluntary memorandum** per new unit and is
chronically under-filed — so the EC register is the more complete census of industrial activity in these
sectors. Metallurgy (7.6×) and chemicals (4.8×) show the widest gaps; pulp & paper (0.2×) is the lone
inversion. This is consistent with the trade repo's standing finding that **IEM under-measures investment**.

Data: `data/iem_ec_activity_comparison.json` · `data/iem_sector_counts_sep2024.json` (DPIIT IEM Statistics
Report, Sep-2024, Annexure-3). Caveat: DPIIT's 39-category DIPP/SIA industry scheme maps *many-to-many* onto
EIA activity codes, not 1:1; the mapping is documented in the JSON.
