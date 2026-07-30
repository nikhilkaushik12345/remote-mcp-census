"""Run one web search per domain that direct probing did not confirm.

Probing only finds servers on guessable hosts. Search covers the rest: endpoints
documented on arbitrary hostnames. Resumable - already-searched domains are skipped,
so an interruption costs nothing. Any https URL containing 'mcp' is kept as a
candidate endpoint for the verification pass that follows.
"""
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

GW = os.environ["V4_GATEWAY_URL"].rstrip("/")
TOK = os.environ["V4_RUN_TOKEN"]
OUT = "work/search_sweep.jsonl"
_lock = threading.Lock()
_l = threading.local()

MCP_HINT = re.compile(r"\bmcp\b|model context protocol", re.I)
URL_RE = re.compile(r"https?://[^\s\)\]\"'<>,]+")


def sess():
    if not hasattr(_l, "s"):
        _l.s = requests.Session()
    return _l.s


def search(query):
    for i in range(3):
        try:
            r = sess().post(f"{GW}/api/v4/search",
                            headers={"Authorization": f"Bearer {TOK}",
                                     "Content-Type": "application/json"},
                            json={"query": query, "num_results": 5}, timeout=70)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 + i * 3)
                continue
            return {"_http": r.status_code}
        except Exception:
            time.sleep(2 + i * 3)
    return None


def brand(domain):
    return domain.split(".")[0].replace("-", " ")


def one(domain):
    q = (f"does {brand(domain)} ({domain}) provide an official hosted remote MCP "
         f"(Model Context Protocol) server, and what is its endpoint URL")
    j = search(q)
    rec = {"domain": domain, "ok": bool(j and "_http" not in j)}
    if not rec["ok"]:
        rec["err"] = (j or {}).get("_http", "fail")
        return rec
    blob = j.get("results")
    blob = blob if isinstance(blob, str) else json.dumps(blob)
    rec["mcp_mentioned"] = bool(MCP_HINT.search(blob))
    root = ".".join(domain.split(".")[-2:])
    cands, fp = [], []
    for u in dict.fromkeys(URL_RE.findall(blob)):
        u = u.rstrip(".,;)")
        if re.search(r"/mcp|mcp\.|-mcp|mcp-|/sse", u, re.I):
            cands.append(u)
        if root.split(".")[0] in u:
            fp.append(u)
    rec["candidates"] = cands[:12]
    rec["first_party"] = fp[:8]
    rec["excerpt"] = blob[:700] if rec["mcp_mentioned"] else ""
    return rec


def main():
    rows = json.load(open("work/rows.json"))
    todo = [r["domain"] for r in rows
            if r["status"] in ("none", "no_dns", "inconclusive")]
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            try:
                done.add(json.loads(line)["domain"])
            except Exception:
                pass
    todo = [d for d in todo if d not in done]
    print(f"to search: {len(todo)} (already done {len(done)})", flush=True)

    fh = open(OUT, "a")
    n = hits = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        for rec in ex.map(one, todo):
            n += 1
            if rec.get("mcp_mentioned") and rec.get("candidates"):
                hits += 1
            with _lock:
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
            if n % 200 == 0:
                print(f"  {n}/{len(todo)} candidate-bearing={hits}", flush=True)
    fh.close()
    print(f"done. searched={n} candidate-bearing={hits}")


if __name__ == "__main__":
    main()
