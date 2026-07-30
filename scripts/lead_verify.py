"""Resolve the 118 'documented but unverified' leads into verdicts.

Each lead is a first-party page that mentions MCP. Fetch it and decide what it
actually describes: a hosted endpoint (extract and probe the URL), a local stdio
package (npx/uvx/docker - out of scope), or merely commentary about MCP.
"""
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3

urllib3.disable_warnings()

UA = {"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "accept": "text/html,application/xhtml+xml,*/*"}
_local = threading.local()

URL_RE = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
REMOTE_HINT = re.compile(r"streamable\s*http|remote\s+mcp|hosted\s+mcp|mcp\s+endpoint|"
                         r"\"url\"\s*:|serverUrl|sse\s+endpoint", re.I)
LOCAL_HINT = re.compile(r"\bnpx\b|\buvx\b|\"command\"\s*:|docker\s+run|pip\s+install|stdio", re.I)


def sess():
    if not hasattr(_local, "s"):
        s = requests.Session()
        s.headers.update(UA)
        s.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=4, max_retries=0))
        _local.s = s
    return _local.s


def endpoint_candidates(text, domain):
    brand = domain.split(".")[0]
    out = []
    for u in URL_RE.findall(text):
        u = u.rstrip(".,;)\"'>").rstrip("\\")
        low = u.lower()
        if "mcp" not in low and not low.endswith("/sse"):
            continue
        if any(b in low for b in ("github.com", "npmjs.com", "glama.ai", "smithery",
                                  "pulsemcp", "mcpservers.org", "cursor.com", "modelcontextprotocol.io",
                                  "anthropic.com", "docs.claude.com", "youtube.com", "reddit")):
            continue
        host = low.split("/")[2] if "://" in low else ""
        if brand not in host and domain.split(".")[0] not in host:
            continue
        if re.search(r"\.(png|jpg|jpeg|svg|css|js|gif|webp)$", low):
            continue
        # keep only plausible endpoints, not doc pages
        if re.search(r"/(mcp|sse)(/|$)|mcp\.[a-z0-9.-]+\.[a-z]{2,}", low):
            out.append(u)
    return list(dict.fromkeys(out))[:8]


def fetch_lead(item):
    domain, urls = item
    rec = {"domain": domain, "pages": [], "endpoints": [], "remote": False, "local": False}
    for u in urls[:4]:
        try:
            r = sess().get(u, timeout=25, verify=False, allow_redirects=True)
            text = r.text if r.status_code == 200 else ""
        except Exception as exc:
            rec["pages"].append({"url": u, "err": type(exc).__name__})
            continue
        rec["pages"].append({"url": u, "status": r.status_code, "len": len(text)})
        if not text:
            continue
        rec["endpoints"] += endpoint_candidates(text, domain)
        if REMOTE_HINT.search(text):
            rec["remote"] = True
        if LOCAL_HINT.search(text):
            rec["local"] = True
    rec["endpoints"] = list(dict.fromkeys(rec["endpoints"]))[:8]
    return rec


def main():
    rows = json.load(open("work/rows.json"))
    leads = [(r["domain"], r["leads"]) for r in rows if r["status"] == "doc_lead"]
    print(f"leads: {len(leads)}", flush=True)
    out, done = [], 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        for rec in ex.map(fetch_lead, leads):
            out.append(rec)
            done += 1
            if rec["endpoints"]:
                print(f"  {rec['domain']:22} -> {rec['endpoints'][:2]}", flush=True)
            if done % 25 == 0:
                print(f"  {done}/{len(leads)}", flush=True)
    json.dump(out, open(sys.argv[1], "w"), indent=1)
    print("with endpoint candidates:", sum(1 for r in out if r["endpoints"]))
    print("remote-worded:", sum(1 for r in out if r["remote"]),
          "| local-worded:", sum(1 for r in out if r["local"]))


if __name__ == "__main__":
    main()
