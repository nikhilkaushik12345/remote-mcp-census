"""Probe exact endpoint candidates surfaced by targeted search."""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from http_stage import fetch
from consolidate import tier

BLOCK = ("github.com", "npmjs.com", "mcpservers.org", "remotemcplist", "apify.com",
         "smithery", "mcp.directory", "medium.com", "deepwiki", "example.com",
         "localhost", "127.0.0.1", "your-", "vinkius", "stackone.com")


def clean(u):
    u = u.replace("`", "").replace("\\n", "").strip().rstrip(".,;:)\"'")
    u = u.replace("}", "")
    if any(x in u.lower() for x in BLOCK) or "<" in u or "…" in u:
        return None
    if not u.startswith("https://"):
        return None
    # Search results include docs/blog URLs containing 'mcp'. Probe only URL shapes
    # that could actually be a transport endpoint.
    host = u.split("/")[2].lower()
    path = "/" + "/".join(u.split("/")[3:])
    if host.startswith("mcp.") or "-mcp." in host or ".mcp." in host:
        return u
    if re.search(r"/(mcp|sse)(/|$|\?)|/ex-mcp/|/sncapps/mcp-server/", path, re.I):
        return u
    return None


def main():
    data = json.load(open("work/targeted_search.json"))
    jobs, seen = [], set()
    for domain, rec in data.items():
        for raw in rec["urls"]:
            u = clean(raw)
            if not u or u in seen:
                continue
            seen.add(u)
            jobs.append((domain, u, "init"))
            prm = u.rstrip("/") + "/.well-known/oauth-protected-resource"
            jobs.append((domain, prm, "prm"))
    print(f"candidate endpoints={len(seen)} probes={len(jobs)}", flush=True)
    out, hits = [], {}
    with ThreadPoolExecutor(max_workers=32) as ex:
        for rec in ex.map(fetch, jobs):
            out.append(rec)
            t = tier(rec)
            if t and t != "ambiguous":
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                print(f"  HIT {t:10} {rec['url']}", flush=True)
    with open(sys.argv[1], "w") as fh:
        for rec in out:
            fh.write(json.dumps(rec) + "\n")
    print(f"\nnewly confirmed domains: {len(hits)}")
    for d, vals in sorted(hits.items()):
        print(f"  {d:24} {vals[0][0]:10} {vals[0][1]}")


if __name__ == "__main__":
    main()
