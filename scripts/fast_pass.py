"""Fast sweep over the still-open leads.

For every documentation host a lead points at, try the patterns that doc platforms
mount MCP on, and mine llms.txt / llms-full.txt (which doc sites publish as plain
text, so no JS rendering is needed) for endpoint URLs. Then probe what turns up.
"""
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3

from http_stage import fetch
from consolidate import tier

urllib3.disable_warnings()

UA = {"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PATHS = ["/~gitbook/mcp", "/mcp", "/api/mcp", "/mcp/mcp"]
TXT = ["/llms.txt", "/llms-full.txt", "/.well-known/mcp.json"]
URL_RE = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
_local = threading.local()


def sess():
    if not hasattr(_local, "s"):
        s = requests.Session()
        s.headers.update(UA)
        s.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=4, max_retries=0))
        _local.s = s
    return _local.s


def mine(item):
    domain, host = item
    found = []
    for p in TXT:
        try:
            r = sess().get(f"https://{host}{p}", timeout=20, verify=False)
        except Exception:
            continue
        if r.status_code != 200 or len(r.text) > 4_000_000:
            continue
        for u in URL_RE.findall(r.text):
            u = u.rstrip(".,;)\"'>`")
            low = u.lower()
            if not re.search(r"/(mcp|sse)(/|$)|//mcp\.", low):
                continue
            if any(b in low for b in ("github", "npmjs", "modelcontextprotocol.io",
                                      "glama", "smithery", "cursor.com", "claude.ai")):
                continue
            found.append(u)
    return domain, list(dict.fromkeys(found))[:10]


def main():
    rows = json.load(open("work/rows.json"))
    openrows = [r for r in rows if r["status"] in ("doc_lead", "review")]
    pages = {p["domain"]: p for p in json.load(open("work/lead_pages.json"))}

    hosts = set()
    for r in openrows:
        for u in (r.get("leads") or []):
            try:
                hosts.add((r["domain"], u.split("/")[2]))
            except IndexError:
                pass
        p = pages.get(r["domain"], {})
        for e in p.get("endpoints", []):
            try:
                hosts.add((r["domain"], e.split("/")[2]))
            except IndexError:
                pass
    print(f"open rows={len(openrows)} doc hosts={len(hosts)}", flush=True)

    mined = {}
    with ThreadPoolExecutor(max_workers=24) as ex:
        for d, urls in ex.map(mine, hosts):
            if urls:
                mined.setdefault(d, []).extend(urls)
                print(f"  mined {d:22} {urls[:2]}", flush=True)

    jobs, seen = [], set()
    for d, h in hosts:
        for p in PATHS:
            u = f"https://{h}{p}"
            if u not in seen:
                seen.add(u)
                jobs.append((d, u, "init"))
    for d, urls in mined.items():
        for u in dict.fromkeys(urls):
            if u not in seen:
                seen.add(u)
                jobs.append((d, u, "init"))
                prm = u.rstrip("/") + "/.well-known/oauth-protected-resource"
                jobs.append((d, prm, "prm"))
    print(f"probes: {len(jobs)}", flush=True)

    out, hits = [], {}
    with ThreadPoolExecutor(max_workers=32) as ex:
        for rec in ex.map(fetch, jobs):
            out.append(rec)
            t = tier(rec)
            if t and t != "ambiguous":
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                print(f"  HIT {t:10} {rec['url']}", flush=True)
    json.dump(out, open(sys.argv[1], "w"), indent=1)
    print(f"\nnewly confirmed domains: {len(hits)}")
    for d, v in sorted(hits.items()):
        print(f"  {d:24} {v[0][0]:10} {v[0][1]}")


if __name__ == "__main__":
    main()
