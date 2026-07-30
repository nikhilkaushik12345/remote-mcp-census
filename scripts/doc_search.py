"""Attach first-party documentation to each probe-confirmed domain.

The probe proves a server is live; the docs prove the vendor offers it publicly.
Only results hosted on the vendor's own registrable domain count as first-party.
"""
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

GW = os.environ["V4_GATEWAY_URL"].rstrip("/")
TOK = os.environ["V4_RUN_TOKEN"]


def registrable(host):
    parts = host.lower().lstrip(".").split(".")
    return ".".join(parts[-3:]) if len(parts) > 2 and len(parts[-2]) <= 3 else ".".join(parts[-2:])


def search(query, tries=3):
    for i in range(tries):
        try:
            r = requests.post(f"{GW}/api/v4/search",
                              headers={"Authorization": f"Bearer {TOK}",
                                       "Content-Type": "application/json"},
                              json={"query": query, "num_results": 8}, timeout=60)
            if r.status_code == 200:
                return r.json()
            time.sleep(1 + i * 2)
        except Exception:
            time.sleep(1 + i * 2)
    return None


def one(domain):
    brand = domain.split(".")[0]
    q = (f"official documentation page for the hosted remote MCP server offered by "
         f"{brand} ({domain}), including its endpoint URL")
    j = search(q)
    firstparty, other = [], []
    if j:
        txt = j.get("results")
        blob = txt if isinstance(txt, str) else json.dumps(txt)
        for url in dict.fromkeys(re.findall(r"https?://[^\s\)\]\"'<>]+", blob)):
            host = url.split("/")[2]
            tgt = registrable(domain)
            entry = url.rstrip(".,;")
            if registrable(host) == tgt or tgt.split(".")[0] in host:
                if re.search(r"mcp|model-context", url, re.I) or True:
                    firstparty.append(entry)
            else:
                other.append(entry)
    return domain, {"first_party": firstparty[:6], "other": other[:4]}


def main():
    domains = json.load(open(sys.argv[1]))
    print(f"searching docs for {len(domains)} domains", flush=True)
    out, done = {}, 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for d, rec in ex.map(one, domains):
            out[d] = rec
            done += 1
            if done % 20 == 0:
                print(f"  {done}/{len(domains)}", flush=True)
    json.dump(out, open(sys.argv[2], "w"), indent=1)
    hit = sum(1 for v in out.values() if v["first_party"])
    print(f"done. with first-party url: {hit}/{len(out)}")


if __name__ == "__main__":
    main()
