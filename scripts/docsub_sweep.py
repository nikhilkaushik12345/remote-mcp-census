"""Sweep documentation subdomains of every still-open domain.

The fast pass found OpenAI, Aruba and Visma on developer(s).<domain>/mcp, so apply
that shape systematically: doc-style subdomains x doc-platform MCP paths.
Resolve first over DoH so only live hosts are probed.
"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

from http_stage import fetch
from consolidate import tier

SUBS = ["docs", "developer", "developers", "help", "support", "learn", "doc",
        "api-docs", "devdocs"]
PATHS = ["/mcp", "/~gitbook/mcp", "/api/mcp"]
_local = threading.local()


def sess():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
    return _local.s


def resolves(host):
    for url, hdr in (("https://cloudflare-dns.com/dns-query", "application/dns-json"),
                     ("https://dns.google/resolve", "application/json")):
        try:
            r = sess().get(url, params={"name": host, "type": "A"},
                           headers={"accept": hdr}, timeout=8)
            if r.status_code != 200:
                continue
            j = r.json()
            if j.get("Status") == 3:
                return False
            if j.get("Status") == 0:
                return any(a.get("type") in (1, 5) for a in (j.get("Answer") or []))
        except Exception:
            continue
    return False


def main():
    rows = json.load(open("work/rows.json"))
    todo = [r["domain"] for r in rows if r["status"] in ("doc_lead", "review")]
    cand = [(d, f"{s}.{d}") for d in todo for s in SUBS]
    print(f"domains={len(todo)} host candidates={len(cand)}", flush=True)

    live = []
    with ThreadPoolExecutor(max_workers=48) as ex:
        for (d, h), ok in zip(cand, ex.map(lambda x: resolves(x[1]), cand)):
            if ok:
                live.append((d, h))
    print(f"live doc hosts: {len(live)}", flush=True)

    jobs = [(d, f"https://{h}{p}", "init") for d, h in live for p in PATHS]
    print(f"probes: {len(jobs)}", flush=True)
    out, hits = [], {}
    with ThreadPoolExecutor(max_workers=36) as ex:
        for rec in ex.map(fetch, jobs):
            out.append(rec)
            t = tier(rec)
            if t and t != "ambiguous":
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                print(f"  HIT {t:10} {rec['url']}", flush=True)
    json.dump(out, open(sys.argv[1], "w"), indent=1)
    print(f"\nnewly confirmed: {len(hits)}")
    for d, v in sorted(hits.items()):
        print(f"  {d:24} {v[0][0]:10} {v[0][1]}")


if __name__ == "__main__":
    main()
