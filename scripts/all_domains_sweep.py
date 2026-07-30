"""Probe EVERY non-confirmed, non-dead corpus domain for remote MCP.

Targets:
  - all status=none with a resolving root
  - all doc_lead / review
  - all inconclusive (retry)

High-yield URL set only (keeps runtime sane at ~2k domains):
  https://mcp.<d>/mcp, /sse, /, /.well-known/oauth-protected-resource
  https://<d>/mcp, /api/mcp, /.well-known/oauth-protected-resource
  https://api.<d>/mcp
  https://docs.<d>/mcp, /~gitbook/mcp
  https://developer(s).<d>/mcp
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "work")
from http_stage import fetch
from consolidate import tier


def urls_for(d):
    out = []
    for host, paths, kinds in [
        (f"mcp.{d}", ["/mcp", "/sse", "/", "/.well-known/oauth-protected-resource"],
         ["init", "init", "init", "prm"]),
        (d, ["/mcp", "/api/mcp", "/.well-known/oauth-protected-resource"],
         ["init", "init", "prm"]),
        (f"api.{d}", ["/mcp"], ["init"]),
        (f"docs.{d}", ["/mcp", "/~gitbook/mcp"], ["init", "init"]),
        (f"developer.{d}", ["/mcp"], ["init"]),
        (f"developers.{d}", ["/mcp"], ["init"]),
    ]:
        for p, k in zip(paths, kinds):
            out.append((d, f"https://{host}{p}", k))
    return out


def main():
    rows = json.load(open("work/rows.json"))
    doh = json.load(open("work/doh.json"))
    targets = []
    for r in rows:
        st = r["status"]
        d = r["domain"]
        if st == "confirmed" or st == "no_dns":
            continue
        if st in ("doc_lead", "review", "inconclusive"):
            targets.append(d)
            continue
        # none: only if root or mcp host might exist
        hosts = doh.get(d, {}).get("hosts", {})
        if hosts.get(d) or hosts.get(f"mcp.{d}") or hosts.get(f"api.{d}"):
            targets.append(d)
        elif hosts.get(d) is None:  # unknown - try anyway
            targets.append(d)

    targets = list(dict.fromkeys(targets))
    jobs, seen = [], set()
    for d in targets:
        for j in urls_for(d):
            if j[1] not in seen:
                seen.add(j[1])
                jobs.append(j)

    print(f"targets={len(targets)} probes={len(jobs)}", flush=True)
    out = open(sys.argv[1], "w")
    hits, done = {}, 0
    with ThreadPoolExecutor(max_workers=64) as ex:
        for rec in ex.map(fetch, jobs):
            done += 1
            out.write(json.dumps(rec) + "\n")
            t = tier(rec)
            if t and t != "ambiguous":
                body = (rec.get("body") or "")[:120].lower()
                if "<html" in body or "<!doctype" in body or "captcha" in body:
                    continue
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                print(f"  HIT {t:10} {rec['domain']:28} {rec['url']}", flush=True)
            if done % 2000 == 0:
                print(f"  {done}/{len(jobs)} hits_domains={len(hits)}", flush=True)
    out.close()
    print(f"\ndone probes={done} domains_with_signal={len(hits)}")
    for d, v in sorted(hits.items()):
        print(f"  {d:28} {v[0][0]:10} {v[0][1]}")


if __name__ == "__main__":
    main()
