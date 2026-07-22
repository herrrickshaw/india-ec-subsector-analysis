#!/usr/bin/env python3
"""Render docs/other_clearances.html -- Forest / Wildlife / CRZ clearances.

Reads data/parivesh_other_clearances.json (built by refresh_other_clearances.py).
Same house style as build_page.py: light/dark tokens, static-first, serif display.
"""
import datetime, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    d = json.load(open(os.path.join(ROOT, "data/parivesh_other_clearances.json")))
    C = d["clearances"]
    fc, wl, crz = C["FC"], C["WLC"], C["CRZ"]
    today = datetime.date.today().isoformat()

    def funnel_bar(f, total):
        order = [("granted", "g"), ("in_process", "p"), ("dead", "d"), ("delisted", "x")]
        segs = "".join(
            f'<span class="seg {cls}" style="width:{(f.get(k,0)/total*100):.2f}%" '
            f'title="{k}: {f.get(k,0):,}"></span>' for k, cls in order if f.get(k, 0))
        return f'<div class="bar">{segs}</div>'

    def card(rec, extra=""):
        f = rec["funnel"]
        tot = rec["total"]
        gr = rec["grant_rate_pct_of_decided"]
        return f"""<div class="card">
 <div class="ctop"><div><div class="clabel">{rec['label']}</div>
   <div class="ccode">{rec['code']} · majorClearanceType</div></div>
   <div class="cbig">{tot:,}</div></div>
 {funnel_bar(f, tot)}
 <div class="crow"><span><b class="g">{f.get('granted',0):,}</b> granted</span>
   <span><b class="p">{f.get('in_process',0):,}</b> in process</span>
   <span><b class="d">{f.get('dead',0):,}</b> dead</span>
   <span><b class="x">{f.get('delisted',0):,}</b> delisted</span></div>
 <div class="grate">Grant rate of decided: <b>{gr}%</b> · {rec['n_states']} states/UTs</div>
 {extra}</div>"""

    # forest area by state table
    fa = fc["forest_area_ha"]
    fstates = "".join(
        f'<tr><td>{r["state"]}</td><td class="num">{r["granted_ha"]:,}</td>'
        f'<td class="num">{r["granted_acres"]:,}</td><td class="num muted">{r["pipeline_ha"]:,}</td></tr>'
        for r in fc["forest_area_by_state"])
    ft = fc["by_form_type"]
    forms = (f'<div class="forms"><b>{ft["fresh_diversion_FormA"]:,}</b> fresh (Form-A) · '
             f'<b>{ft["re_diversion_FormE"]:,}</b> re-diversion (Form-E) · '
             f'<b>{ft["renewal_FormBD"]:,}</b> renewal · <b>{ft["transfer_FormF"]:,}</b> transfer</div>')
    ua = "".join(f'<tr><td>{r["agency"]}</td><td class="num">{r["proposals"]:,}</td></tr>'
                 for r in fc["top_user_agencies"])

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>India Forest, Wildlife & CRZ clearances — PARIVESH</title>
<style>
:root{{--bg:#eef1ea;--surface:#fcfcfa;--ink:#14180f;--ink2:#4f5348;--muted:#82867a;--rule:#d7dace;
 --accent:#1f5f5b;--g:#2f7d4f;--p:#c98a1f;--d:#a5402c;--x:#9a9e90;--chip:#eef2ec;
 --serif:"Iowan Old Style",Georgia,serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
 --sans:-apple-system,"Segoe UI",Helvetica,sans-serif;}}
@media(prefers-color-scheme:dark){{:root{{--bg:#12151a;--surface:#1a1e21;--ink:#f2f1ea;--ink2:#c1c4b7;
 --muted:#8b8f83;--rule:#2a2e28;--accent:#6fb3ac;--g:#7bc496;--p:#dcab55;--d:#e08268;--x:#5c6156;--chip:#232a25;}}}}
:root[data-theme=dark]{{--bg:#12151a;--surface:#1a1e21;--ink:#f2f1ea;--ink2:#c1c4b7;--muted:#8b8f83;
 --rule:#2a2e28;--accent:#6fb3ac;--g:#7bc496;--p:#dcab55;--d:#e08268;--x:#5c6156;--chip:#232a25;}}
:root[data-theme=light]{{--bg:#eef1ea;--surface:#fcfcfa;--ink:#14180f;--ink2:#4f5348;--muted:#82867a;
 --rule:#d7dace;--accent:#1f5f5b;--g:#2f7d4f;--p:#c98a1f;--d:#a5402c;--x:#9a9e90;--chip:#eef2ec;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.55}}
.wrap{{max-width:1000px;margin:0 auto;padding:40px 20px 60px}}
.eyebrow{{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}}
h1{{font-family:var(--serif);font-weight:500;font-size:clamp(25px,3.3vw,34px);margin:6px 0 8px}}
h2{{font-family:var(--serif);font-weight:500;font-size:21px;margin:34px 0 6px}}
.dek{{color:var(--ink2);font-size:15px;max-width:78ch}}
a{{color:var(--accent)}}
.cards{{display:grid;grid-template-columns:1fr;gap:16px;margin:22px 0}}
@media(min-width:760px){{.cards{{grid-template-columns:1fr 1fr 1fr}}}}
.card{{background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:16px}}
.ctop{{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}}
.clabel{{font-family:var(--serif);font-size:18px}}.ccode{{font-family:var(--mono);font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
.cbig{{font-family:var(--serif);font-size:30px;color:var(--accent);line-height:1}}
.bar{{display:flex;height:12px;border-radius:6px;overflow:hidden;margin:12px 0 8px;background:var(--chip);gap:1.5px}}
.seg{{display:block;height:100%}}.seg.g{{background:var(--g)}}.seg.p{{background:var(--p)}}.seg.d{{background:var(--d)}}.seg.x{{background:var(--x)}}
.crow{{display:flex;flex-wrap:wrap;gap:10px;font-size:11.5px;color:var(--ink2)}}
.crow b{{font-family:var(--mono)}}.g{{color:var(--g)}}.p{{color:var(--p)}}.d{{color:var(--d)}}.x{{color:var(--x)}}
.grate{{font-size:12px;color:var(--muted);margin-top:10px;border-top:1px dashed var(--rule);padding-top:8px}}
.forms{{font-size:12px;color:var(--ink2);margin-top:8px}}.forms b{{font-family:var(--mono);color:var(--ink)}}
.big-forest{{background:var(--surface);border:1px solid var(--rule);border-left:4px solid var(--g);
 border-radius:10px;padding:16px 18px;margin:8px 0 4px;display:flex;flex-wrap:wrap;gap:26px;align-items:baseline}}
.big-forest .n{{font-family:var(--serif);font-size:34px;color:var(--g)}}.big-forest .l{{font-size:12.5px;color:var(--muted)}}
table{{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:6px}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--rule)}}
th{{font-family:var(--mono);font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);font-weight:400}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono);font-size:12.5px}}
td.muted{{color:var(--muted)}}.scroll{{overflow-x:auto}}
.two{{display:grid;grid-template-columns:1fr;gap:22px}}@media(min-width:820px){{.two{{grid-template-columns:1.5fr 1fr}}}}
.note{{color:var(--muted);font-size:12.5px;border-top:1px dashed var(--rule);margin-top:34px;padding-top:14px;max-width:84ch}}
.back{{font-family:var(--mono);font-size:12px}}
</style></head><body><div class="wrap">
<div class="eyebrow">PARIVESH 2.0 · beyond Environmental Clearance · generated {today}</div>
<h1>India's other green clearances — Forest, Wildlife & CRZ</h1>
<p class="dek">The same open PARIVESH API that serves Environmental Clearances serves three more central
clearances. Together they are the full green-clearance funnel a project passes through — and Forest Clearance
carries something EC does not: <b>the actual area of land</b>, in hectares.
<a class="back" href="./index.html">← back to EC sub-sector analysis</a></p>

<div class="cards">
{card(fc, forms)}
{card(wl)}
{card(crz)}
</div>

<h2>Forest Clearance is a second land-creation channel</h2>
<p class="dek">Every Environmental Clearance answers "may this project pollute?"; Forest Clearance answers "may
this project <i>take</i> this forest land?" — so it is the one register that measures land <b>quantum</b>.
Of the 1.05 million ha in the pipeline (inflated by delisted applications and one ~74,000-ha outlier), the
trustworthy figure is the forest land with <b>final diversion orders granted</b>:</p>
<div class="big-forest">
 <div><div class="n">{fa['granted']:,} ha</div><div class="l">forest land — final diversion granted</div></div>
 <div><div class="n">{fa['acres_granted']:,}</div><div class="l">acres, granted</div></div>
 <div><div class="n">{fc['funnel'].get('granted',0):,}</div><div class="l">approved proposals of {fc['total']:,}</div></div>
</div>
<p class="dek" style="font-size:13px">For scale: the entire national <i>industrial</i> land bank shows ~253,720
developed-and-vacant acres. Forest diversion adds ~{fa['acres_granted']:,} more acres of granted land-use
change — a different channel (mining, linear infra, hydro), on a different clock.</p>

<div class="two">
<div><h2>Forest area by state</h2><div class="scroll"><table>
<thead><tr><th>State / UT</th><th class="num">Granted ha</th><th class="num">Granted acres</th><th class="num">Pipeline ha</th></tr></thead>
<tbody>{fstates}</tbody></table></div></div>
<div><h2>Top user agencies (FC)</h2><div class="scroll"><table>
<thead><tr><th>Agency</th><th class="num">Proposals</th></tr></thead><tbody>{ua}</tbody></table></div></div>
</div>

<h2>What the three funnels say</h2>
<p class="dek">
<b>Forest ({fc['grant_rate_pct_of_decided']}% of decided granted)</b> — 88% are fresh Form-A diversions, but
40% of the register is auto-delisted, so the live decided pool is smaller than the headline count.
<b>Wildlife ({wl['grant_rate_pct_of_decided']}% granted)</b> is the real bottleneck: {wl['funnel'].get('in_process',0):,}
of {wl['total']:,} sit in process, most "Pending at Proponent" — projects near protected areas stall here for the
National/State Board for Wildlife recommendation. <b>CRZ ({crz['grant_rate_pct_of_decided']}%)</b> is small and
coastal ({crz['n_states']} states/UTs) — the gate for ports, coastal industry and waterfront projects.</p>

<div class="note">
Source — <b>PARIVESH 2.0</b> open API (<code>advanceSearchData?majorClearanceType=2|3|4</code>), full Forest /
Wildlife / CRZ registers, fetched {d['built']}. Grant rate = granted ÷ (granted + in-process); 'dead'
(rejected/withdrawn/returned) and 'delisted' (PARIVESH auto-cleanup) are excluded from the denominator, as in the
EC analysis. FC 'granted' = "Final Diversion Order Issued" or "Stage-II Accorded"; Stage-I in-principle is not
counted. The forest-area pipeline total mixes all statuses and is skewed by a single ~74,000-ha outlier — the
granted figure is the reliable one. Pipeline snapshot, not a time series. Data + refresh:
<a href="https://github.com/herrrickshaw/india-ec-subsector-analysis">github.com/herrrickshaw/india-ec-subsector-analysis</a>.
Corrections are displayed, never silent.
</div>
</div></body></html>"""
    open(os.path.join(ROOT, "docs/other_clearances.html"), "w").write(html)
    print(f"docs/other_clearances.html: FC/WL/CRZ, forest granted {fa['granted']:,} ha")


if __name__ == "__main__":
    main()
