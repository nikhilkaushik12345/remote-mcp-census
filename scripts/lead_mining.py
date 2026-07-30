"""Turn search leads into verified endpoints.

Phase 1: fetch each first-party page the search surfaced and scrape endpoint-shaped
         URLs out of its text (docs pages state the endpoint even when the search
         snippet does not).
Phase 2: probe every candidate with a real initialize call plus PRM lookup.
Only first-party hosts are considered; blog/doc URLs are mined, never reported as
endpoints themselves.
"""
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3

from http_stage import fetch

urllib3.disable_warnings()
UA = {"user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126 Safari/537.36"}
URL_RE = re.compile(r"https?://[a-zA-Z0-9._\-]+(?:/[^\s\"'`<>\)\]\},]*)?")
DOCISH = re.compile(r"/blog|/learn|/academy|/news|\.html?$|\.md$|/press|/article", re.I)
ENDPOINTISH = re.compile(r"(/mcp(/|$|\?)|/mcp$|/sse(/|$)|/v1/mcp|/api/mcp|mcp\.[a-z0-9\-]+\.)", re.I)
_l = threading.local()


def reg(host):
    p = host.lower().split(":")[0].split(".")
    return ".".join(p[-3:]) if len(p) > 2 and len(p[-2]) <= 3 else ".".join(p[-2:])


def sess():
    if not hasattr(_l, "s"):
        _l.s = requests.Session()
    return _l.s


def page_urls(args):
    """Fetch a lead page and return first-party endpoint-shaped URLs found in it."""
    domain, url = args
    found = set()
    try:
        r = sess().get(url, headers=UA, timeout=20, verify=False, allow_redirects=True)
        if r.status_code != 200:
            return domain, []
        text = r.text[:400_000]
    except Exception:
        return domain, []
    root = reg(domain)
    for u in URL_RE.findall(text):
        u = u.rstrip("`.,;)\"'").replace("\\", "")
        if len(u) > 200:
            continue
        try:
            host = u.split("/")[2]
        except IndexError:
            continue
        if reg(host) != root or DOCISH.search(u) or not ENDPOINTISH.search(u):
            continue
        found.add(u)
    return domain, sorted(found)[:8]


def main():
    leads = json.load(open("../work/search_leads.json"))

    # phase 1 - mine the lead pages
    jobs = [(d, u) for d, urls in leads.items() for u in urls[:3]]
    print(f"fetching {len(jobs)} lead pages", flush=True)
    mined = {}
    with ThreadPoolExecutor(max_workers=24) as ex:
        for d, urls in ex.map(page_urls, jobs):
            if urls:
                mined.setdefault(d, set()).update(urls)
    mined = {d: sorted(v)[:8] for d, v in mined.items()}
    print(f"domains with mined endpoint URLs: {len(mined)}")

    # candidates = mined URLs + endpoint-shaped URLs straight from the search results
    cands = {d: set(v) for d, v in mined.items()}
    for d, urls in leads.items():
        for u in urls:
            u = u.rstrip("`.,;)\"'")
            if ENDPOINTISH.search(u) and not DOCISH.search(u):
                cands.setdefault(d, set()).add(u)
    total = sum(len(v) for v in cands.values())
    print(f"candidate endpoints: {total} across {len(cands)} domains", flush=True)
    json.dump({d: sorted(v) for d, v in cands.items()},
              open("../work/lead_candidates.json", "w"), indent=1)

    # phase 2 - probe them
    jobs2 = []
    for d, urls in cands.items():
        for u in sorted(urls):
            jobs2.append((d, u, "init"))
            base = "/".join(u.split("/")[:3])
            jobs2.append((d, f"{base}/.well-known/oauth-protected-resource", "prm"))
    seen, uniq = set(), []
    for j in jobs2:
        if j[1] not in seen:
            seen.add(j[1])
            uniq.append(j)
    print(f"probing {len(uniq)} urls", flush=True)
    out = open("../work/http5.jsonl", "w")
    n = 0
    with ThreadPoolExecutor(max_workers=40) as ex:
        for rec in ex.map(fetch, uniq):
            n += 1
            out.write(json.dumps(rec) + "\n")
            if rec.get("signal"):
                print(f"  HIT {rec['signal']:9} {rec['url']}", flush=True)
    out.close()
    print("done", n)


if __name__ == "__main__":
    main()
