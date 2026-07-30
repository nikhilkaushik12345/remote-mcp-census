"""Probe browser-mined endpoints, but only those the lead domain actually owns.

Vendor doc pages routinely cite other vendors' servers (Zendesk's page lists Asana
and Stripe; Android's lists Figma). Crediting those would be wrong, so an endpoint
counts only when its host sits on the lead domain's own registrable domain.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from http_stage import fetch
from consolidate import tier


def reg(host):
    p = host.lower().split(".")
    return ".".join(p[-3:]) if len(p) > 2 and len(p[-2]) <= 3 else ".".join(p[-2:])


def owned(url, domain):
    try:
        host = url.split("/")[2].lower()
    except IndexError:
        return False
    if host in ("127.0.0.1", "localhost") or host.startswith("127."):
        return False
    return reg(host) == reg(domain) or host.endswith("." + domain) or host == domain


def main():
    recs = []
    for f in sys.argv[1:-1]:
        recs += json.load(open(f))

    jobs, seen, kept = [], set(), {}
    for r in recs:
        eps = [e for e in r["endpoints"] if owned(e, r["domain"])]
        # a bare mcp.* host on the right domain is worth probing at /mcp and /sse
        extra = []
        for e in eps:
            host = e.split("/")[2]
            if host.startswith("mcp.") or ".mcp." in host or "mcp" in host:
                extra += [f"https://{host}/mcp", f"https://{host}/sse", f"https://{host}/"]
        for u in dict.fromkeys(eps + extra):
            u = u.rstrip("/") if u.count("/") > 3 else u
            if re.search(r"\[|tenant_id|your-|127\.0\.0\.1|localhost", u):
                continue
            kept.setdefault(r["domain"], []).append(u)
            for v in dict.fromkeys([u, u.rstrip("/") + "/mcp"]):
                if v not in seen:
                    seen.add(v)
                    jobs.append((r["domain"], v, "init"))
            prm = u.rstrip("/") + "/.well-known/oauth-protected-resource"
            if prm not in seen:
                seen.add(prm)
                jobs.append((r["domain"], prm, "prm"))

    print(f"domains with owned candidates: {len(kept)} | probes: {len(jobs)}", flush=True)
    out, hits = [], {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        for rec in ex.map(fetch, jobs):
            out.append(rec)
            t = tier(rec)
            if t and t != "ambiguous":
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                print(f"  HIT {t:10} {rec['url']}", flush=True)
    json.dump(out, open(sys.argv[-1], "w"), indent=1)
    print(f"\nnewly confirmed domains: {len(hits)}")
    for d, v in sorted(hits.items()):
        print(f"  {d:22} {v[0][0]:10} {v[0][1]}")


if __name__ == "__main__":
    main()
