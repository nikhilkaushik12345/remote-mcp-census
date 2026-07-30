"""Stage 2: send a real MCP `initialize` JSON-RPC handshake to every candidate URL.

Positive signals, strongest first:
  oauth_prm  - /.well-known/oauth-protected-resource returns MCP-style OAuth metadata
  handshake  - JSON-RPC reply carrying protocolVersion/serverInfo (a live MCP server)
  mcp_401    - 401/403 whose WWW-Authenticate points at resource_metadata (protected MCP)
  mcp_error  - JSON-RPC error shape (MCP server present, rejecting this exact request)
Everything is written to JSONL so partial progress survives an interruption.
"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3

urllib3.disable_warnings()

INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "mcp-corpus-audit", "version": "1.0"}},
}
HDRS = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
    "user-agent": "Mozilla/5.0 (compatible; mcp-audit/1.0)",
}
_local = threading.local()
_lock = threading.Lock()


def sess():
    if not hasattr(_local, "s"):
        s = requests.Session()
        s.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=4, max_retries=0))
        _local.s = s
    return _local.s


def classify(kind, status, headers, body):
    low = body[:4000].lower()
    wa = (headers.get("www-authenticate") or "").lower()
    if kind == "prm":
        if status == 200 and ("authorization_servers" in low or '"resource"' in low):
            return "oauth_prm"
        return None
    if "resource_metadata" in wa:
        return "mcp_401"
    if "jsonrpc" in low:
        if "protocolversion" in low or "serverinfo" in low:
            return "handshake"
        if '"error"' in low:
            return "mcp_error"
    if status in (401, 403) and ("mcp" in wa or "bearer" in wa) and "mcp" in low:
        return "mcp_401"
    return None


def fetch(job):
    domain, url, kind = job
    rec = {"domain": domain, "url": url, "kind": kind}
    try:
        if kind == "prm":
            r = sess().get(url, headers={"accept": "application/json",
                                        "user-agent": HDRS["user-agent"]},
                           timeout=12, allow_redirects=True, verify=False)
        else:
            r = sess().post(url, json=INIT, headers=HDRS, timeout=12,
                            allow_redirects=True, verify=False)
        body = r.text[:4000]
        rec.update(status=r.status_code, ctype=r.headers.get("content-type", "")[:80],
                   wa=(r.headers.get("www-authenticate") or "")[:300],
                   body=body[:600], final=r.url[:300])
        rec["signal"] = classify(kind, r.status_code, r.headers, body)
    except Exception as exc:
        rec.update(status=None, error=type(exc).__name__)
        rec["signal"] = None
    return rec


def build_jobs(doh):
    jobs = []
    for d, rec in doh.items():
        hosts, wild = rec["hosts"], rec["wildcard"]
        if hosts.get(f"mcp.{d}"):
            for p in ("/mcp", "/sse", "/"):
                jobs.append((d, f"https://mcp.{d}{p}", "init"))
            jobs.append((d, f"https://mcp.{d}/.well-known/oauth-protected-resource", "prm"))
        if hosts.get(d) and not wild:
            jobs.append((d, f"https://{d}/mcp", "init"))
            jobs.append((d, f"https://{d}/.well-known/oauth-protected-resource", "prm"))
        if hosts.get(f"api.{d}") and not wild:
            jobs.append((d, f"https://api.{d}/mcp", "init"))
    return jobs


def main():
    doh = json.load(open(sys.argv[1]))
    jobs = build_jobs(doh)
    print(f"probes: {len(jobs)}", flush=True)
    out = open(sys.argv[2], "w")
    hits = done = 0
    with ThreadPoolExecutor(max_workers=56) as ex:
        for rec in ex.map(fetch, jobs):
            done += 1
            if rec["signal"]:
                hits += 1
                print(f"  HIT {rec['signal']:9} {rec['url']}", flush=True)
            with _lock:
                out.write(json.dumps(rec) + "\n")
            if done % 500 == 0:
                print(f"  {done}/{len(jobs)} hits={hits}", flush=True)
    out.close()
    print(f"done. probes={done} hits={hits}")


if __name__ == "__main__":
    main()
