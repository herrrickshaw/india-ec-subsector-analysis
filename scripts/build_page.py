#!/usr/bin/env python3
"""Render docs/index.html — state-wise Environmental Clearances by sub-sector.

Generated from data/ec_subsector_analysis.json + data/ec_state_subsector_matrix.json.
House style: light/dark theme, static-first (works without JS), a sub-sector filter
that repivots the state table client-side from an embedded compact matrix.
"""
import datetime, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    an = json.load(open(os.path.join(ROOT, "data/ec_subsector_analysis.json")))
    mx = json.load(open(os.path.join(ROOT, "data/ec_state_subsector_matrix.json")))
    subs = an["subsector_analysis"]
    today = datetime.date.today().isoformat()

    # compact matrix for client-side repivot: {activity: {state: {status: n}}}
    piv = {}
    for c in mx["matrix"]:
        piv.setdefault(c["activity"], {}).setdefault(c["state"], {})[c["status"]] = c["count"]

    def rows_for(sub):
        chips = "".join(
            f'<span class="chip">{s["state"]} <b>{s["granted"]:,}</b> · {s["share_pct"]}%</span>'
            for s in sub["top_states"])
        gr = sub["grant_rate_pct"]
        grcls = "hi" if gr and gr >= 65 else "lo" if gr and gr < 40 else ""
        return (f'<tr data-act="{sub["activity"]}">'
                f'<td class="code">{sub["activity"]}</td>'
                f'<td>{sub["label"]}</td>'
                f'<td class="num">{sub["total"]:,}</td>'
                f'<td class="num">{sub["granted"]:,}</td>'
                f'<td class="num pct {grcls}">{gr:.0f}%</td>'
                f'<td class="lead">{chips}</td></tr>')

    body_rows = "\n".join(rows_for(s) for s in subs)
    opts = "\n".join(f'<option value="{s["activity"]}">{s["activity"]} — {s["label"][:40]}</option>' for s in subs)
    st_tot = an["state_totals"][:12]
    st_rows = "".join(f'<tr><td>{r["state"]}</td><td class="num">{r["total"]:,}</td></tr>' for r in st_tot)

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>India Environmental Clearances — state × sub-sector</title>
<style>
:root{{--bg:#eef1ea;--surface:#fcfcfa;--ink:#14180f;--ink2:#4f5348;--muted:#82867a;
  --rule:#d7dace;--accent:#1f5f5b;--accent-soft:#dbe9e6;--hi:#2f7d4f;--lo:#a5402c;--chip:#eef2ec;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;--serif:"Iowan Old Style",Georgia,serif;
  --sans:-apple-system,"Segoe UI",Helvetica,sans-serif;}}
@media(prefers-color-scheme:dark){{:root{{--bg:#12151a;--surface:#1a1e21;--ink:#f2f1ea;--ink2:#c1c4b7;
  --muted:#8b8f83;--rule:#2a2e28;--accent:#6fb3ac;--accent-soft:#20342f;--hi:#7bc496;--lo:#e08268;--chip:#232a25;}}}}
:root[data-theme=dark]{{--bg:#12151a;--surface:#1a1e21;--ink:#f2f1ea;--ink2:#c1c4b7;--muted:#8b8f83;
  --rule:#2a2e28;--accent:#6fb3ac;--accent-soft:#20342f;--hi:#7bc496;--lo:#e08268;--chip:#232a25;}}
:root[data-theme=light]{{--bg:#eef1ea;--surface:#fcfcfa;--ink:#14180f;--ink2:#4f5348;--muted:#82867a;
  --rule:#d7dace;--accent:#1f5f5b;--accent-soft:#dbe9e6;--hi:#2f7d4f;--lo:#a5402c;--chip:#eef2ec;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.55}}
.wrap{{max-width:1080px;margin:0 auto;padding:40px 20px 60px}}
.eyebrow{{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}}
h1{{font-family:var(--serif);font-weight:500;font-size:clamp(26px,3.4vw,36px);margin:6px 0 8px}}
.dek{{color:var(--ink2);font-size:15px;max-width:76ch}}
.stats{{display:flex;gap:26px;flex-wrap:wrap;margin:22px 0}}
.stat .n{{font-family:var(--serif);font-size:30px;color:var(--accent)}}.stat .l{{font-size:12.5px;color:var(--muted)}}
.controls{{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--rule);padding:12px 0;margin:14px 0;z-index:5}}
select,input{{background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:6px;padding:7px 10px;font:inherit}}
table{{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:6px}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--rule);vertical-align:top}}
th{{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:400}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono);font-size:12.5px}}
td.code{{font-family:var(--mono);color:var(--accent);white-space:nowrap}}
td.pct.hi{{color:var(--hi);font-weight:600}}td.pct.lo{{color:var(--lo);font-weight:600}}
.chip{{display:inline-block;background:var(--chip);border-radius:99px;padding:2px 9px;margin:2px 4px 2px 0;font-size:11.5px;color:var(--ink2);white-space:nowrap}}
.scroll{{overflow-x:auto}}.two{{display:grid;grid-template-columns:1fr;gap:24px}}@media(min-width:820px){{.two{{grid-template-columns:2.4fr 1fr}}}}
h2{{font-family:var(--serif);font-weight:500;font-size:20px;margin:28px 0 4px}}
.note{{color:var(--muted);font-size:12.5px;border-top:1px dashed var(--rule);margin-top:34px;padding-top:14px;max-width:82ch;font-family:var(--sans)}}
a{{color:var(--accent)}}.hidden{{display:none}}
#stateview{{margin-top:8px}}
</style></head><body><div class="wrap">
<div class="eyebrow">Environmental Clearance analysis · generated {today}</div>
<h1>India's Environmental Clearances, by state and sub-sector</h1>
<p class="dek">The full national Environmental Clearance register from PARIVESH 2.0 — <b>{mx['total_proposals']:,}
proposals</b> across <b>{mx['n_states']} states/UTs</b> and <b>{len(subs)} EIA-schedule sub-sectors</b> — pivoted to
show which state leads each sub-sector and how grant rates differ by activity. One open API call; refreshable.</p>
<div class="stats">
 <div class="stat"><div class="n">{mx['total_proposals']:,}</div><div class="l">EC proposals</div></div>
 <div class="stat"><div class="n">{len(subs)}</div><div class="l">sub-sectors analysed</div></div>
 <div class="stat"><div class="n">{mx['n_states']}</div><div class="l">states / UTs</div></div>
 <div class="stat"><div class="n">{sum(s['granted'] for s in subs):,}</div><div class="l">clearances granted</div></div>
</div>

<div class="controls">
 <label style="font-size:13px;color:var(--ink2)">Repivot the state table by sub-sector:
 <select id="pick"><option value="">— pick a sub-sector —</option>{opts}</select></label>
</div>
<div id="stateview" class="hidden scroll"></div>

<h2>Sub-sectors, ranked by volume</h2>
<p class="dek" style="font-size:13.5px">Grant rate = granted ÷ (granted + ToR-granted + in-process); PARIVESH auto-delisted
applications are excluded from that denominator. <span style="color:var(--hi)">Green ≥65%</span>,
<span style="color:var(--lo)">rust &lt;40%</span>. "Leaders" are shares of that sub-sector's granted clearances.</p>
<div class="scroll"><table>
<thead><tr><th>Code</th><th>Sub-sector (EIA activity)</th><th class="num">Total</th><th class="num">Granted</th>
<th class="num">Grant %</th><th>Leading states (share of grants)</th></tr></thead>
<tbody>{body_rows}</tbody></table></div>

<div class="two">
<div></div>
<div><h2>Top states, all sub-sectors</h2><div class="scroll"><table>
<thead><tr><th>State / UT</th><th class="num">EC proposals</th></tr></thead><tbody>{st_rows}</tbody></table></div></div>
</div>

<div class="note">
Source — <b>PARIVESH 2.0</b> open API (<code>parivesh.nic.in/parivesh_api/trackYourProposal/advanceSearchData?majorClearanceType=1</code>),
full Environmental Clearance register, fetched {mx['built']}. Sub-sector = the EIA-schedule Activity code carried on each
proposal ("1(a) Mining of minerals", "5(f) Synthetic organic chemicals", …). {mx.get('unclassified_activity',0):,} proposals
carry no parseable activity code and are excluded from the sub-sector view but kept in state totals.
"Delisted" ({sum(piv.get(a,{}).get(s,{}).get('delisted',0) for a in piv for s in piv[a]):,} proposals) is PARIVESH's
auto-cleanup of inactive applications — excluded from grant-rate denominators. Data + refresh script:
<a href="https://github.com/herrrickshaw/india-ec-subsector-analysis">github.com/herrrickshaw/india-ec-subsector-analysis</a>.
Corrections are displayed, never silent.
</div>

<script>
const PIV={json.dumps(piv, separators=(',',':'))};
const LABELS={json.dumps({s['activity']: s['label'] for s in subs})};
const ORD=["granted","tor_granted","in_process","dead","delisted"];
const HDR={{granted:"Granted",tor_granted:"ToR granted",in_process:"In process",dead:"Dead",delisted:"Delisted"}};
document.getElementById('pick').addEventListener('change',e=>{{
  const a=e.target.value, box=document.getElementById('stateview');
  if(!a){{box.classList.add('hidden');return}}
  const states=Object.entries(PIV[a]||{{}}).map(([st,b])=>{{
    const live=(b.granted||0)+(b.tor_granted||0)+(b.in_process||0);
    return {{st, b, tot:ORD.reduce((s,k)=>s+(b[k]||0),0), gr: live? (b.granted||0)/live*100 : null}};
  }}).sort((x,y)=>y.tot-x.tot);
  let h='<h2 style="margin-top:18px">'+a+' — '+LABELS[a]+' · by state</h2><table><thead><tr><th>State / UT</th>'
    +ORD.map(k=>'<th class=num>'+HDR[k]+'</th>').join('')+'<th class=num>Grant %</th></tr></thead><tbody>';
  for(const r of states){{
    h+='<tr><td>'+r.st.charAt(0)+r.st.slice(1).toLowerCase()+'</td>'
      +ORD.map(k=>'<td class=num>'+(r.b[k]||0).toLocaleString()+'</td>').join('')
      +'<td class="num pct '+(r.gr>=65?'hi':r.gr<40?'lo':'')+'">'+(r.gr==null?'—':Math.round(r.gr)+'%')+'</td></tr>';
  }}
  box.innerHTML=h+'</tbody></table>'; box.classList.remove('hidden');
  box.scrollIntoView({{behavior:'smooth',block:'nearest'}});
}});
</script>
</div></body></html>"""
    open(os.path.join(ROOT, "docs/index.html"), "w").write(html)
    print(f"docs/index.html: {len(subs)} sub-sectors, {mx['n_states']} states, client-side repivot")


if __name__ == "__main__":
    main()
