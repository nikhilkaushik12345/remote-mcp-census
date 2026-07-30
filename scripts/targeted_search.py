"""Run several endpoint-focused searches over the unresolved corpus leads."""
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

GW = os.environ["V4_GATEWAY_URL"].rstrip("/")
TOK = os.environ["V4_RUN_TOKEN"]
URL_RE = re.compile(r"https?://[^\s\)\]\"'<>,]+")
_local = threading.local()


def sess():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
    return _local.s


def search(domain, query):
    for delay in (0, 2, 5):
        if delay:
            time.sleep(delay)
        try:
            r = sess().post(
                f"{GW}/api/v4/search",
                headers={"Authorization": f"Bearer {TOK}", "Content-Type": "application/json"},
                json={"query": query, "num_results": 10}, timeout=80)
            if r.status_code == 200:
                blob = r.json().get("results", "")
                return domain, query, blob if isinstance(blob, str) else json.dumps(blob)
        except Exception:
            pass
    return domain, query, ""


def main():
    rows = json.load(open("work/rows.json"))
    domains = [r["domain"] for r in rows if r["status"] in ("doc_lead", "review")]
    jobs = []
    for d in domains:
        jobs += [
            (d, f"official {d} remote MCP server exact endpoint URL configuration"),
            (d, f"site:{d} MCP server URL streamable HTTP SSE endpoint"),
            (d, f"site:{d} model context protocol mcpServers url"),
        ]
    print(f"domains={len(domains)} searches={len(jobs)}", flush=True)
    data = {d: {"urls": [], "excerpts": []} for d in domains}
    with ThreadPoolExecutor(max_workers=10) as ex:
        fs = [ex.submit(search, *j) for j in jobs]
        done = 0
        for f in as_completed(fs):
            d, q, blob = f.result()
            done += 1
            if blob:
                data[d]["excerpts"].append(blob[:1800])
                for u in URL_RE.findall(blob):
                    u = u.rstrip(".,;:)")
                    if re.search(r"/mcp|mcp\.|-mcp|mcp-|/sse", u, re.I):
                        data[d]["urls"].append(u)
            if done % 50 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
    for d in data:
        data[d]["urls"] = list(dict.fromkeys(data[d]["urls"]))
    json.dump(data, open("work/targeted_search.json", "w"), indent=1)
    hits = [(d, v["urls"]) for d, v in data.items() if v["urls"]]
    print(f"candidate-bearing domains: {len(hits)}")
    for d, urls in hits:
        print(f"  {d:24} {urls[:3]}")


if __name__ == "__main__":
    main()
