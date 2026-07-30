"""Fast first-party-only sweep of every still-open domain.

1. Endpoint-focused web search per domain.
2. Standard host/path pattern probes on first-party hosts only.
3. Mine llms.txt on docs hosts.
Nothing on a third-party host is ever attributed to a corpus domain.
"""
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
import urllib3

urllib3.disable_warnings()

sys.path.insert(0, "work")
from http_stage import fetch
from consolidate import tier

GW = os.environ["V4_GATEWAY_URL"].rstrip("/")
TOK = os.environ["V4_RUN_TOKEN"]
UA = {"user-agent": "Mozilla/5.0 (compatible; mcp-audit/1.0)"}
URL_RE = re.compile(r"https?://[A-Za-z0-9._~:/\-?#\[\]@!$&'()*+,;=%]+")
BLOCK = re.compile(
    r"github\.com|npmjs|mcpserver|smithery|glama\.ai|pipedream|cursor\.com|"
    r"modelcontextprotocol\.io|anthropic\.com|claude\.ai|medium\.com|"
    r"linkedin\.com|youtube\.com|reddit\.com|stackoverflow|"
    r"example\.com|localhost|127\.0\.0\.1|mintlify\.me|"
    r"vercel\.app|workers\.dev|ngrok|cloudflareworkers",
    re.I,
)
SUBS = ["", "mcp", "api", "docs", "developer", "developers", "dev", "help",
        "support", "learn", "doc", "app", "platform", "cloud"]
PATHS = ["/mcp", "/v1/mcp", "/api/mcp", "/sse", "/mcp/sse", "/~gitbook/mcp",
         "/.well-known/oauth-protected-resource"]
_local = threading.local()


def sess():
    if not hasattr(_local, "s"):
        s = requests.Session()
        s.headers.update(UA)
        s.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=6, max_retries=0))
        _local.s = s
    return _local.s


def registrable(host):
    p = host.lower().split(".")
    if len(p) >= 3 and len(p[-2]) <= 3:
        return ".".join(p[-3:])
    return ".".join(p[-2:]) if len(p) >= 2 else host


def first_party(domain, url):
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    if not host or BLOCK.search(host) or BLOCK.search(url):
        return False
    dreg = registrable(domain)
    hreg = registrable(host)
    brand = domain.split(".")[0].lower()
    if hreg == dreg or host == domain or host.endswith("." + domain):
        return True
    # brand match on sibling TLD (notion.so vs notion.com style) — require brand in host
    if brand and len(brand) >= 4 and brand in host.split(".")[0]:
        # still reject if host is clearly another product
        return hreg.split(".")[0] == brand or host.startswith("mcp.")
    return False


def search(domain):
    brand = domain.split(".")[0]
    qs = [
        f'site:{domain} "mcp" (endpoint OR "streamable http" OR "mcp server" OR sse)',
        f'"{domain}" OR "mcp.{domain}" remote MCP server endpoint url',
        f'{brand} hosted remote MCP server "https://" mcp official documentation',
    ]
    urls = []
    for q in qs:
        for attempt in range(3):
            try:
                r = sess().post(
                    f"{GW}/api/v4/search",
                    headers={"Authorization": f"Bearer {TOK}",
                             "Content-Type": "application/json"},
                    json={"query": q, "num_results": 8}, timeout=45,
                )
                if r.status_code == 200:
                    blob = r.text
                    for u in URL_RE.findall(blob):
                        u = u.rstrip(".,;)]}\"'>`")
                        urls.append(u)
                    break
            except Exception:
                time.sleep(1 + attempt)
    return list(dict.fromkeys(urls))


def mine_llms(host):
    found = []
    for p in ("/llms.txt", "/llms-full.txt", "/.well-known/mcp.json"):
        try:
            r = sess().get(f"https://{host}{p}", timeout=12, verify=False)
            if r.status_code != 200 or len(r.text) > 2_000_000:
                continue
            for u in URL_RE.findall(r.text):
                u = u.rstrip(".,;)]}\"'>`")
                if re.search(r"/(mcp|sse)(/|$)|//mcp\.", u, re.I):
                    found.append(u)
        except Exception:
            pass
    return found


def build_pattern_jobs(domain):
    jobs = []
    for sub in SUBS:
        host = f"{sub}.{domain}" if sub else domain
        for path in PATHS:
            kind = "prm" if "well-known" in path else "init"
            jobs.append((domain, f"https://{host}{path}", kind))
    return jobs


def main():
    rows = json.load(open("work/rows.json"))
    open_rows = [r for r in rows if r["status"] in ("doc_lead", "review")]
    domains = [r["domain"] for r in open_rows]
    print(f"open domains: {len(domains)}", flush=True)

    # 1) searches
    search_urls = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(search, d): d for d in domains}
        done = 0
        for fut in as_completed(futs):
            d = futs[fut]
            try:
                search_urls[d] = fut.result()
            except Exception as e:
                search_urls[d] = []
                print(f"  search fail {d}: {e}", flush=True)
            done += 1
            if done % 15 == 0:
                print(f"  searched {done}/{len(domains)}", flush=True)
    print("searches done", flush=True)

    # 2) collect first-party endpoint candidates + pattern jobs
    jobs, seen = [], set()
    for d in domains:
        for j in build_pattern_jobs(d):
            if j[1] not in seen:
                seen.add(j[1])
                jobs.append(j)
        for u in search_urls.get(d, []):
            if not first_party(d, u):
                continue
            # keep endpoint-like or well-known
            if re.search(r"/(mcp|sse)(/|$)|//mcp\.|oauth-protected-resource", u, re.I):
                if u not in seen:
                    seen.add(u)
                    kind = "prm" if "well-known" in u else "init"
                    jobs.append((d, u, kind))
            # also try /mcp on any first-party host found
            try:
                host = urlparse(u).hostname
                if host:
                    for p in ("/mcp", "/api/mcp", "/v1/mcp",
                              "/.well-known/oauth-protected-resource"):
                        cand = f"https://{host}{p}"
                        if cand not in seen:
                            seen.add(cand)
                            kind = "prm" if "well-known" in p else "init"
                            jobs.append((d, cand, kind))
            except Exception:
                pass

    # llms.txt on docs.* hosts
    llms_hosts = [(d, f"docs.{d}") for d in domains] + \
                 [(d, f"developer.{d}") for d in domains] + \
                 [(d, f"developers.{d}") for d in domains]
    with ThreadPoolExecutor(max_workers=20) as ex:
        for (d, host), found in zip(llms_hosts, ex.map(lambda x: mine_llms(x[1]), llms_hosts)):
            for u in found:
                if first_party(d, u) and u not in seen:
                    seen.add(u)
                    jobs.append((d, u, "init"))

    print(f"probes: {len(jobs)}", flush=True)
    out_path = sys.argv[1]
    hits = {}
    written = 0
    with open(out_path, "w") as out, ThreadPoolExecutor(max_workers=48) as ex:
        for rec in ex.map(fetch, jobs):
            # force domain attribution only if first-party
            if not first_party(rec["domain"], rec["url"]):
                continue
            out.write(json.dumps(rec) + "\n")
            written += 1
            t = tier(rec)
            if t and t != "ambiguous":
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                print(f"  HIT {t:10} {rec['domain']:22} {rec['url']}", flush=True)
            if written % 400 == 0:
                print(f"  wrote {written}", flush=True)

    print(f"\nwrote {written} first-party probe records")
    print(f"domains with signal: {len(hits)}")
    for d, v in sorted(hits.items()):
        print(f"  {d:24} {v[0][0]:10} {v[0][1]}")
    json.dump({d: search_urls[d] for d in domains}, open("work/final_search_urls.json", "w"), indent=1)


if __name__ == "__main__":
    main()
