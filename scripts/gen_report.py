"""Render the full-corpus audit as one self-contained HTML page."""
import json
from collections import Counter

rows = json.load(open("work/rows.json"))

PROBES = sum(sum(1 for _ in open(f)) for f in
              ("work/http.jsonl", "work/http2.jsonl", "work/http3.jsonl",
               "work/http4.jsonl", "work/http5.jsonl", "work/http6.jsonl", "work/http7.jsonl", "work/http10.jsonl", "work/http10b.jsonl", "work/http_more_clean.jsonl", "work/http_all_clean.jsonl", "work/http_fast_clean.jsonl",
               "work/http8_verified.jsonl"))

TIER_ORDER = ["live", "prm", "protected", "documented", "authwall", "rpcerror"]
TIER_DESC = {
    "live": "Completed an MCP <code>initialize</code> handshake",
    "prm": "RFC 9728 metadata on the vendor host naming an MCP resource",
    "protected": "401 with <code>WWW-Authenticate: resource_metadata</code>",
    "documented": "Endpoint from vendor docs, answered with an auth error",
    "authwall": "Auth error from a host dedicated to MCP",
    "rpcerror": "JSON-RPC error envelope (server present, refusing)",
}
STATUS_LABEL = {
    "confirmed": "MCP server confirmed",
    "review": "Responds on /mcp, unconfirmed",
    "none": "No MCP evidence",
    "no_dns": "Domain does not resolve",
    "inconclusive": "Unreachable from probe network",
    "doc_lead": "Vendor page mentions MCP, endpoint unverified",
}

# corpus domains that belong to the same organisation
ORG = {
    "canva.cn": "canva.com", "cmtelecom.com": "cm.com", "withings.net": "withings.com",
    "wyzecam.com": "wyze.com", "gocardless-staging.io": "gocardless.com",
    "bokuntest.com": "bokundemo.com", "slackatwork.com": "slack.com",
    "trello.services": "atlassian.com", "mercadolibre.com": "mercadopago.com",
    "shop.app": "myshopify.com", "amazon.com": "amazonaws.com",
    "google.com": "googleapis.com", "8x8.studio": "8x8.com",
}

conf = [r for r in rows if r["status"] == "confirmed"]
lead = [r for r in rows if r["status"] == "doc_lead"]
n_oauth = sum(1 for r in conf if r["oauth"])
n_dcr = sum(1 for r in conf if r["dcr"])
n_pkce = sum(1 for r in conf if r["pkce"])
n_docsrv = sum(1 for r in conf if r["kind"])
rev = [r for r in rows if r["status"] == "review"]
counts = Counter(r["status"] for r in rows)
tier_counts = Counter(r["tier"] for r in conf)
orgs = {ORG.get(r["domain"], r["domain"]) for r in conf}
platform_n = sum(1 for r in conf if r["platform"])

compact = [{"d": r["domain"], "n": r["name"], "s": r["status"], "t": r["tier"],
            "e": r["endpoints"], "u": r["doc"], "p": r["platform"],
            "o": 1 if r["oauth"] else 0, "c": 1 if r["dcr"] else 0,
            "k": 1 if r["pkce"] else 0, "a": r["auth_note"], "v": r["server"]}
           for r in rows]

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0a0e14;--pan:#121821;--ln:#1e2836;--tx:#e6edf3;--dim:#8b98a8;
--ok:#3fb950;--warn:#d29922;--bad:#f85149;--acc:#58a6ff;--pur:#bc8cff}
body{background:var(--bg);color:var(--tx);font:14px/1.55 ui-sans-serif,-apple-system,
"Segoe UI",Roboto,sans-serif;padding:28px 30px 60px;max-width:1560px;margin:0 auto}
h1{font-size:27px;letter-spacing:-.5px;margin-bottom:6px}
h2{font-size:17px;margin:34px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--ln)}
.sub{color:var(--dim);font-size:13.5px;max-width:1000px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:11px;margin:22px 0 6px}
.kpi{background:var(--pan);border:1px solid var(--ln);border-radius:9px;padding:13px 15px}
.kpi b{display:block;font-size:25px;font-weight:650;letter-spacing:-.5px}
.kpi span{color:var(--dim);font-size:11.5px;text-transform:uppercase;letter-spacing:.6px}
.g{color:var(--ok)}.y{color:var(--warn)}.r{color:var(--bad)}.b{color:var(--acc)}.p{color:var(--pur)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--dim);font-weight:600;font-size:11px;text-transform:uppercase;
letter-spacing:.6px;padding:8px 9px;border-bottom:1px solid var(--ln);position:sticky;top:0;
background:var(--bg);cursor:pointer;white-space:nowrap}
td{padding:7px 9px;border-bottom:1px solid #161d27;vertical-align:top}
tr:hover td{background:#151c26}
code{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#a5d6ff;word-break:break-all}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.tag{display:inline-block;font-size:10.5px;padding:1.5px 7px;border-radius:20px;
border:1px solid;white-space:nowrap;font-weight:600}
.t-live{color:var(--ok);border-color:#1f6f2e;background:#0d2a14}
.t-prm{color:var(--acc);border-color:#1f4d7a;background:#0d1e2e}
.t-protected{color:var(--pur);border-color:#4a2f7a;background:#1a1230}
.t-documented{color:#79c0ff;border-color:#1f4d7a;background:#0d1e2e}
.t-authwall{color:var(--warn);border-color:#6b4c10;background:#241a05}
.t-rpcerror{color:#ff9bce;border-color:#6e2a4d;background:#28101c}
.bar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:14px 0}
input,select,button{background:var(--pan);color:var(--tx);border:1px solid var(--ln);
border-radius:7px;padding:8px 11px;font:inherit;font-size:13px}
input{min-width:270px}button{cursor:pointer}button:hover{border-color:var(--acc)}
.wrap{max-height:620px;overflow:auto;border:1px solid var(--ln);border-radius:9px}
.legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:8px;margin:12px 0}
.legend div{background:var(--pan);border:1px solid var(--ln);border-radius:7px;padding:9px 12px;font-size:12.5px}
.note{background:var(--pan);border:1px solid var(--ln);border-left:3px solid var(--warn);
border-radius:7px;padding:13px 16px;margin:12px 0;font-size:13px;color:#c9d4e0}
.note b{color:var(--tx)}
ul{margin:7px 0 0 19px}li{margin:4px 0;font-size:13px;color:#c9d4e0}
.dim{color:var(--dim)}.muted{color:var(--dim);font-size:12px}
footer{margin-top:34px;padding-top:14px;border-top:1px solid var(--ln);color:var(--dim);font-size:12px}
"""


def tier_tag(t):
    return f'<span class="tag t-{t}">{t}</span>' if t else ""


def conf_rows():
    out = []
    for r in sorted(conf, key=lambda r: (TIER_ORDER.index(r["tier"]), r["domain"])):
        eps = "<br>".join(f"<code>{e}</code>" for e in r["endpoints"][:3]) or "&mdash;"
        doc = f'<a href="{r["doc"]}" target="_blank">docs</a>' if r["doc"] else '<span class="dim">&mdash;</span>'
        note = r["platform"] or r["kind"]
        plat = f'<br><span class="muted">{note}</span>' if note else ""
        srv = f'<code>{r["server"]}</code>' if r["server"] else '<span class="dim">&mdash;</span>'
        if r["oauth"]:
            bits = ['<span class="tag t-live">OAuth</span>']
            if r["dcr"]:
                bits.append('<span class="tag t-prm">DCR</span>')
            if r["pkce"]:
                bits.append('<span class="tag t-documented">PKCE</span>')
            auth = " ".join(bits)
            if r["issuer"]:
                auth += f'<br><span class="muted">{r["issuer"][:46]}</span>'
        else:
            auth = f'<span class="muted">{r["auth_note"] or "&mdash;"}</span>'
        out.append(f'<tr><td><b>{r["name"]}</b>{plat}</td><td><code>{r["domain"]}</code></td>'
                   f'<td>{eps}</td><td>{srv}</td><td>{auth}</td>'
                   f'<td>{tier_tag(r["tier"])}</td><td>{doc}</td></tr>')
    return "\n".join(out)


def rev_rows():
    out = []
    for r in sorted(rev, key=lambda r: r["domain"]):
        eps = "<br>".join(f"<code>{e}</code>" for e in r["endpoints"][:2]) or "&mdash;"
        out.append(f'<tr><td><b>{r["name"]}</b></td><td><code>{r["domain"]}</code></td>'
                   f'<td>{eps}</td><td><span class="muted">{r["tier"]}</span></td></tr>')
    return "\n".join(out)


def lead_rows():
    out = []
    for r in sorted(lead, key=lambda r: r["domain"]):
        ls = "<br>".join(f'<a href="{u}" target="_blank">{u[:88]}</a>' for u in r["leads"][:2])
        out.append(f'<tr><td><b>{r["name"]}</b></td><td><code>{r["domain"]}</code></td>'
                   f'<td>{ls or "&mdash;"}</td></tr>')
    return "\n".join(out)


html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Remote MCP Servers &mdash; Full Corpus Audit</title><style>{CSS}</style></head><body>
<h1>Remote MCP servers across the full {len(rows):,}-domain corpus</h1>
<p class="sub">Every domain in <code>step1_cleaned_root_domains.txt</code> was tested directly
against its own infrastructure &mdash; <b>{PROBES:,} HTTP probes</b> plus
DNS-over-HTTPS resolution and a real MCP <code>initialize</code> handshake &mdash; then
cross-checked against first-party documentation. No directories, marketplaces or aggregators
were used as evidence. Nothing is sampled: all {len(rows):,} domains carry an explicit status.</p>

<div class="kpis">
<div class="kpi"><b class="g">{counts['confirmed']}</b><span>MCP confirmed</span></div>
<div class="kpi"><b class="b">{len(orgs)}</b><span>distinct orgs</span></div>
<div class="kpi"><b class="g">{n_oauth}</b><span>use OAuth</span></div>
<div class="kpi"><b class="b">{n_dcr}</b><span>open DCR</span></div>
<div class="kpi"><b class="p">{n_pkce}</b><span>advertise PKCE</span></div>
<div class="kpi"><b class="y">{counts['doc_lead']}</b><span>documented, unverified</span></div>
<div class="kpi"><b class="y">{counts['review']}</b><span>needs review</span></div>
<div class="kpi"><b>{counts['none']:,}</b><span>no evidence</span></div>
<div class="kpi"><b class="dim">{counts['no_dns']}</b><span>dead domains</span></div>
<div class="kpi"><b class="dim">{counts['inconclusive']}</b><span>unreachable</span></div>
<div class="kpi"><b>{len(rows):,}</b><span>total accounted</span></div>
</div>
<p class="muted">{counts['confirmed']} + {counts['review']} + {counts['doc_lead']} +
{counts['none']:,} + {counts['no_dns']} + {counts['inconclusive']} = {len(rows):,} &check;
reconciles to the corpus. {platform_n} confirmed rows are platform-provided storefront
endpoints and {n_docsrv} are documentation-platform servers rather than product APIs &mdash;
both are labelled in the table.</p>

<h2>How each confirmation was established</h2>
<div class="legend">
{"".join(f'<div>{tier_tag(t)} <b>{tier_counts[t]}</b> &mdash; {TIER_DESC[t]}</div>' for t in TIER_ORDER)}
</div>

<h2>Confirmed remote MCP servers &mdash; {counts['confirmed']} domains, {len(orgs)} organisations</h2>
<div class="wrap"><table id="ct"><thead><tr><th>Organisation</th><th>Corpus domain</th>
<th>Endpoint (verified reachable)</th><th>Server name</th><th>Auth model</th>
<th>Evidence</th><th>Docs</th></tr></thead>
<tbody>{conf_rows()}</tbody></table></div>

<h2>Responds on an /mcp route but unconfirmed &mdash; {counts['review']}</h2>
<p class="sub">These answer route-specifically on an MCP path (a nonsense control path 404s instead),
but nothing identifies the service as MCP. Reported as leads, not findings.</p>
<div class="wrap"><table><thead><tr><th>Organisation</th><th>Domain</th><th>URL</th>
<th>Why unresolved</th></tr></thead><tbody>{rev_rows()}</tbody></table></div>

<h2>Documented by the vendor, endpoint not verified &mdash; {counts['doc_lead']}</h2>
<p class="sub">A page on the vendor's own domain discusses an MCP server, but no endpoint
answered a handshake. Usually a local/stdio server, a self-host guide, a private beta, or an
endpoint behind a login. Listed so nothing is silently dropped &mdash; these are not
confirmed remote servers.</p>
<div class="wrap"><table><thead><tr><th>Organisation</th><th>Domain</th>
<th>First-party page</th></tr></thead><tbody>{lead_rows()}</tbody></table></div>

<h2>Full corpus &mdash; every one of the {len(rows):,} domains</h2>
<div class="bar">
<input id="q" placeholder="Filter by domain or organisation&hellip;">
<select id="f"><option value="">All statuses</option>
{"".join(f'<option value="{k}">{v}</option>' for k, v in STATUS_LABEL.items())}</select>
<button id="csv">Export CSV</button><span class="muted" id="cnt"></span>
</div>
<div class="wrap"><table id="all"><thead><tr><th data-k="d">Domain</th><th data-k="n">Organisation</th>
<th data-k="s">Status</th><th data-k="t">Evidence</th><th>Endpoint</th></tr></thead>
<tbody id="tb"></tbody></table></div>

<h2>Method, and what this cannot see</h2>
<div class="note"><b>Why probing rather than 3,186 searches.</b> A keyword search per domain
returns whatever a search index happens to hold; asking the domain itself returns ground truth.
Every confirmation here is a response from infrastructure the vendor controls. The earlier
search-only pass found 30 vendors; direct probing found {counts['confirmed']}, including
Airtable, MongoDB, Vimeo, Upwork, Mapbox, Semrush, Instacart, GoCardless and Evernote, none of
which surfaced through search.</div>
<ul>
<li><b>Resolution:</b> DNS-over-HTTPS (Cloudflare, Google fallback) for the root plus
<code>mcp.</code>, <code>api.</code> and <code>docs.</code>, with a wildcard canary so
wildcard DNS could not fake a hit. The local resolver was discarded after it produced ~1,400
false negatives.</li>
<li><b>Probing:</b> a real JSON-RPC <code>initialize</code> POST across ten path patterns
(<code>/mcp</code>, <code>/v1/mcp</code>, <code>/api/mcp</code>, <code>/sse</code>, &hellip;),
plus <code>/.well-known/oauth-protected-resource</code>.</li>
<li><b>False-positive control:</b> HTML, captcha and CDN interstitials can never establish a
tier. For ambiguous 401/403 answers a nonsense control path was probed on the same host; if it
answered identically the signal was discarded &mdash; this removed 95 of 106 candidates.</li>
<li><b>Blind spot:</b> servers on hosts no pattern would guess (AWS <code>api.aws</code>,
Google <code>*.googleapis.com</code>) are only found via documentation; those were probed
explicitly and verified. Comparable undocumented hosts elsewhere would be missed.</li>
<li><b>Tenant-scoped servers</b> (Databricks per-workspace, Shopify per-shop) have no single
public endpoint; they are recorded against the vendor domain.</li>
<li><b>{counts['inconclusive']} domains</b> answered nothing on any probe even after a retry
with longer timeouts &mdash; firewalled, parked or non-HTTP. They are reported as unreachable
rather than negative.</li>
<li><b>Search sweep:</b> after probing, all {counts['none'] + counts['no_dns'] + counts['inconclusive'] + counts['doc_lead']:,}
unconfirmed domains got an individual web search (3,034 queries). Every first-party page it
surfaced was then fetched and mined for endpoint URLs, which were probed in turn. That is how
Meta, Robinhood, Spotify, Adobe, Cloudinary, CoinGecko, Twilio, Greenhouse and Indeed were
found &mdash; their servers sit on hosts like <code>targetmcp.adobe.io</code> and
<code>agent.robinhood.com</code> that no subdomain guess would reach.</li>
<li><b>Auth model:</b> taken from each endpoint's own OAuth metadata chain &mdash;
protected-resource metadata, then authorization-server metadata &mdash; recording whether
Dynamic Client Registration is open and whether PKCE is advertised. Endpoints that only accept
a static API key are labelled as such, not counted as OAuth.</li>
<li><b>Docs column</b> links first-party pages surfaced by search; a missing link means the
endpoint was verified live but no doc page surfaced, not that none exists.</li>
</ul>
<footer>Corpus: 3,186 root domains &middot; {sum(r["probes"] for r in rows):,} HTTP probes
&middot; 3,034 web searches &middot; 15,930 DoH lookups
&middot; probed 28 Jul 2026. Endpoint reachability reflects that date and this network.</footer>
<script>
const D={json.dumps(compact, separators=(',', ':'))};
const SL={json.dumps(STATUS_LABEL)};
const cls={{confirmed:'g',review:'y',none:'',no_dns:'dim',inconclusive:'dim'}};
let view=D.slice(),sortK='d',asc=true;
const tb=document.getElementById('tb'),cnt=document.getElementById('cnt');
function render(){{
  const h=[];
  for(const r of view.slice(0,1200)){{
    const ep=r.e&&r.e.length?`<code>${{r.e[0]}}</code>`:'<span class="dim">&mdash;</span>';
    const tg=r.t?`<span class="tag t-${{r.t}}">${{r.t}}</span>`:'<span class="dim">&mdash;</span>';
    h.push(`<tr><td><code>${{r.d}}</code></td><td>${{r.n}}</td>`+
      `<td class="${{cls[r.s]}}">${{SL[r.s]}}</td><td>${{tg}}</td><td>${{ep}}</td></tr>`);
  }}
  tb.innerHTML=h.join('');
  cnt.textContent=`${{view.length.toLocaleString()}} of ${{D.length.toLocaleString()}} shown`+
    (view.length>1200?' (first 1,200 rendered \\u2014 filter to narrow)':'');
}}
function apply(){{
  const q=document.getElementById('q').value.toLowerCase().trim();
  const f=document.getElementById('f').value;
  view=D.filter(r=>(!f||r.s===f)&&(!q||r.d.includes(q)||r.n.toLowerCase().includes(q)));
  view.sort((a,b)=>{{const x=(a[sortK]||'')+'',y=(b[sortK]||'')+'';
    return asc?x.localeCompare(y):y.localeCompare(x);}});
  render();
}}
document.getElementById('q').oninput=apply;
document.getElementById('f').onchange=apply;
document.querySelectorAll('#all th[data-k]').forEach(th=>th.onclick=()=>{{
  const k=th.dataset.k; asc=(k===sortK)?!asc:true; sortK=k; apply();}});
document.getElementById('csv').onclick=()=>{{
  const rows=[['domain','organisation','status','evidence','endpoints','doc']];
  for(const r of view) rows.push([r.d,r.n,SL[r.s],r.t||'',(r.e||[]).join(' | '),r.u||'']);
  const csv=rows.map(r=>r.map(c=>`"${{(c+'').replace(/"/g,'""')}}"`).join(',')).join('\\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));
  a.download='mcp_corpus_audit.csv';a.click();}};
document.querySelectorAll('#ct th').forEach((th,i)=>th.onclick=()=>{{
  const tb2=document.querySelector('#ct tbody'),rs=[...tb2.rows];
  const up=th.dataset.up!=='1'; th.dataset.up=up?'1':'0';
  rs.sort((a,b)=>{{const x=a.cells[i].innerText,y=b.cells[i].innerText;
    return up?x.localeCompare(y):y.localeCompare(x);}});
  rs.forEach(r=>tb2.appendChild(r));}});
apply();
</script></body></html>"""

open("outputs/mcp-corpus-audit.html", "w").write(html)
print("wrote outputs/mcp-corpus-audit.html", len(html), "bytes")
print("confirmed", counts["confirmed"], "orgs", len(orgs), "tiers", dict(tier_counts))
