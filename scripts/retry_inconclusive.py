"""Re-probe domains where every earlier request failed at the network level,
with longer timeouts, so 'inconclusive' reflects reality and not transient errors."""
import json
from concurrent.futures import ThreadPoolExecutor

import http_stage
from http_stage import fetch

http_stage.__dict__.setdefault("_", None)

rows = json.load(open("../work/rows.json"))
targets = [r["domain"] for r in rows if r["status"] == "inconclusive"]
doh = json.load(open("../work/doh.json"))

jobs = []
for d in targets:
    hosts = doh.get(d, {}).get("hosts", {})
    if hosts.get(d) is not False:
        jobs.append((d, f"https://{d}/mcp", "init"))
        jobs.append((d, f"https://{d}/.well-known/oauth-protected-resource", "prm"))
    if hosts.get(f"mcp.{d}"):
        jobs.append((d, f"https://mcp.{d}/mcp", "init"))
        jobs.append((d, f"https://mcp.{d}/.well-known/oauth-protected-resource", "prm"))
    if hosts.get(f"api.{d}"):
        jobs.append((d, f"https://api.{d}/mcp", "init"))

print(f"domains={len(targets)} probes={len(jobs)}", flush=True)
out = open("../work/http4.jsonl", "w")
answered = set()
with ThreadPoolExecutor(max_workers=24) as ex:
    for rec in ex.map(fetch, jobs):
        out.write(json.dumps(rec) + "\n")
        if rec.get("status") is not None:
            answered.add(rec["domain"])
        if rec.get("signal"):
            print(f"  HIT {rec['signal']} {rec['url']}", flush=True)
out.close()
print(f"now answering: {len(answered)}/{len(targets)}")
