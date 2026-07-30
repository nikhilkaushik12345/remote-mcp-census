"""Aggressive re-probe of every non-confirmed domain.

Includes status=none with few prior probes, open leads, inconclusive, and
wildcard-DNS domains (root paths only). Broader path set than all_domains_sweep.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "work")
from http_stage import fetch
from consolidate import tier

# Skip obvious non-org TLD fragments from the cleaned list
SKIP = set("""
co.uk co.jp co.kr co.nz co.th co.il co.ke co.id com.au com.br com.mx com.ar
com.tw com.do com.cn org.uk org.au net.au gov.uk edu.au ac.uk
""".split())

PATHS_MCP = ["/mcp", "/sse", "/", "/v1/mcp", "/api/mcp",
             "/.well-known/oauth-protected-resource"]
PATHS_ROOT = ["/mcp", "/api/mcp", "/v1/mcp", "/sse",
              "/.well-known/oauth-protected-resource"]
PATHS_DOCS = ["/mcp", "/~gitbook/mcp", "/api/mcp", "/docs/mcp"]
PATHS_API = ["/mcp", "/v1/mcp", "/v2/mcp", "/api/mcp", "/sse"]


def jobs_for(d, doh_rec):
    hosts = (doh_rec or {}).get("hosts", {})
    wild = (doh_rec or {}).get("wildcard")
    out = []
    def add(host, paths, kinds=None):
        for i, p in enumerate(paths):
            k = "prm" if "well-known" in p else "init"
            out.append((d, f"https://{host}{p}", k))

    # Always try mcp. even if DNS said no (DoH can be stale/wrong)
    add(f"mcp.{d}", PATHS_MCP)
    # Root and api if not pure wildcard noise, or always try root paths
    add(d, PATHS_ROOT)
    add(f"api.{d}", PATHS_API)
    add(f"docs.{d}", PATHS_DOCS)
    add(f"developer.{d}", ["/mcp", "/api/mcp"])
    add(f"developers.{d}", ["/mcp", "/api/mcp"])
    add(f"dev.{d}", ["/mcp"])
    add(f"app.{d}", ["/mcp", "/api/mcp"])
    add(f"platform.{d}", ["/mcp"])
    add(f"cloud.{d}", ["/mcp"])
    add(f"agent.{d}", ["/mcp"])
    add(f"ai.{d}", ["/mcp"])
    add(f"gateway.{d}", ["/mcp"])
    add(f"stream.{d}", ["/mcp", "/sse"])
    return out


def main():
    rows = json.load(open("work/rows.json"))
    doh = json.load(open("work/doh.json"))

    # Already-seen URLs from prior full sweep to avoid pure duplicate work
    # but we WANT re-probe of domains that only had shallow coverage
    targets = []
    for r in rows:
        if r["status"] == "confirmed" or r["status"] == "no_dns":
            continue
        d = r["domain"]
        if d in SKIP:
            continue
        targets.append(d)
    targets = list(dict.fromkeys(targets))

    jobs, seen = [], set()
    for d in targets:
        for j in jobs_for(d, doh.get(d)):
            if j[1] not in seen:
                seen.add(j[1])
                jobs.append(j)

    print(f"targets={len(targets)} probes={len(jobs)}", flush=True)
    out = open(sys.argv[1], "w", buffering=1)
    hits, done = {}, 0
    with ThreadPoolExecutor(max_workers=72) as ex:
        for rec in ex.map(fetch, jobs):
            done += 1
            try:
                out.write(json.dumps(rec) + "\n")
            except Exception as e:
                print("write fail", e, flush=True)
                continue
            t = tier(rec)
            if t and t != "ambiguous":
                body = (rec.get("body") or "")[:100].lower()
                if any(x in body for x in ("<html", "<!doctype", "captcha", "just a moment")):
                    continue
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                if len(hits[rec["domain"]]) == 1:
                    print(f"  HIT {t:10} {rec['domain']:30} {rec['url']}", flush=True)
            if done % 3000 == 0:
                print(f"  {done}/{len(jobs)} domains_hit={len(hits)}", flush=True)
    out.close()
    print(f"\ndone probes={done} domains={len(hits)}")
    for d, v in sorted(hits.items()):
        print(f"  {d:30} {v[0][0]:10} {v[0][1]}")


if __name__ == "__main__":
    main()
