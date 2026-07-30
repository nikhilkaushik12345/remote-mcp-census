"""Probe every endpoint URL mined from the lead pages, plus obvious variants."""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from http_stage import fetch
from consolidate import tier


def variants(u):
    u = re.sub(r"&quot.*$", "", u).rstrip("/")
    if re.search(r"\[|\]|your-path|tenant_id", u):
        return []
    out = [u]
    if not u.endswith("/mcp"):
        out.append(u + "/mcp")
    out.append(u + "/")
    return out


def main():
    leads = json.load(open(sys.argv[2]))
    jobs, seen = [], set()
    for rec in leads:
        for e in rec["endpoints"]:
            for v in variants(e):
                if v not in seen:
                    seen.add(v)
                    jobs.append((rec["domain"], v, "init"))
                prm = v.rstrip("/") + "/.well-known/oauth-protected-resource"
                if prm not in seen:
                    seen.add(prm)
                    jobs.append((rec["domain"], prm, "prm"))
    print(f"probes: {len(jobs)}", flush=True)

    out, hits = [], {}
    with ThreadPoolExecutor(max_workers=24) as ex:
        for rec in ex.map(fetch, jobs):
            out.append(rec)
            t = tier(rec)
            if t:
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                print(f"  HIT {t:10} {rec['url']}", flush=True)
    json.dump(out, open(sys.argv[1], "w"), indent=1)
    print(f"\ndomains newly confirmed: {len(hits)}")
    for d, v in sorted(hits.items()):
        print(f"  {d:22} {v[0][0]:10} {v[0][1]}")


if __name__ == "__main__":
    main()
