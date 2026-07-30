"""Stage 2b: close the gaps left by the first HTTP pass.

1. /api/mcp on every live root - Shopify storefront MCP and other platforms mount there.
2. Root + api.* probes for wildcard-DNS domains, which pass 1 wrongly skipped
   (a wildcard only invalidates subdomain DNS evidence, not the root site itself).
3. Domains whose DNS answer was inconclusive get probed anyway.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from http_stage import fetch

_lock_out = []


def build(doh):
    jobs = []
    for d, rec in doh.items():
        hosts, wild = rec["hosts"], rec["wildcard"]
        root_live = hosts.get(d) is not False  # True or unknown
        if root_live:
            jobs.append((d, f"https://{d}/api/mcp", "init"))
        if wild and root_live:
            jobs.append((d, f"https://{d}/mcp", "init"))
            jobs.append((d, f"https://{d}/.well-known/oauth-protected-resource", "prm"))
            jobs.append((d, f"https://api.{d}/mcp", "init"))
        if hosts.get(d) is None:
            jobs.append((d, f"https://{d}/mcp", "init"))
            jobs.append((d, f"https://{d}/.well-known/oauth-protected-resource", "prm"))
    seen, uniq = set(), []
    for j in jobs:
        if j[1] not in seen:
            seen.add(j[1])
            uniq.append(j)
    return uniq


def main():
    doh = json.load(open(sys.argv[1]))
    jobs = build(doh)
    print(f"probes: {len(jobs)}", flush=True)
    out = open(sys.argv[2], "w")
    done = hits = 0
    with ThreadPoolExecutor(max_workers=56) as ex:
        for rec in ex.map(fetch, jobs):
            done += 1
            if rec["signal"]:
                hits += 1
                print(f"  HIT {rec['signal']:9} {rec['url']}", flush=True)
            out.write(json.dumps(rec) + "\n")
            if done % 500 == 0:
                print(f"  {done}/{len(jobs)} hits={hits}", flush=True)
    out.close()
    print(f"done. probes={done} hits={hits}")


if __name__ == "__main__":
    main()
