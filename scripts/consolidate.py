"""Final consolidation: fold all probe passes into one evidence tier per domain.

Tiers, strongest first:
  live      - server completed an MCP initialize handshake
  prm       - RFC 9728 metadata on the vendor's host naming an MCP resource
  protected - 401 whose WWW-Authenticate points at resource_metadata
  authwall  - 401/403 (JSON, not an HTML/CDN block) from an MCP-dedicated host+path
  rpcerror  - JSON-RPC error envelope: a server is there, refusing this request

Rejected: HTML bodies, captcha/CDN interstitials, catch-all 200s. A bot-block 403
is not evidence of anything, so HTML is never allowed to establish a tier.
"""
import json
import re
import sys
from collections import defaultdict

HTMLISH = re.compile(r"<!doctype|<html|captcha|just a moment", re.I)

from http_pass3 import DOC_URLS
DOCSET = {u.rstrip("/") for urls in DOC_URLS.values() for u in urls}
ORDER = ["live", "prm", "protected", "documented", "authwall", "rpcerror", "ambiguous"]


def jparse(body):
    b = (body or "").strip()
    if not b.startswith(("{", "[")):
        # SSE framing. Some servers emit "event: message\ndata: {...}", others put
        # the whole frame on one line, so anchoring 'data:' to line start loses them.
        m = re.search(r"data:\s*(\{.*)", b, re.S)
        if not m:
            return None
        b = m.group(1).strip()
    for cut in (len(b), b.rfind("}") + 1):
        try:
            return json.loads(b[:cut])
        except Exception:
            continue
    return None


def mcp_dedicated(url):
    """Only a host that exists to serve MCP counts. A /mcp path on a general API
    host is ambiguous - a WAF 403 there proves nothing - so it is reviewed instead."""
    host = url.split("/")[2]
    return (host.startswith(("mcp.", "mcp-")) or ".mcp." in host or
            "-mcp." in host)


def tier(rec):
    body, ctype = rec.get("body") or "", (rec.get("ctype") or "").lower()
    wa, status, url = (rec.get("wa") or "").lower(), rec.get("status"), rec["url"]
    if status is None or HTMLISH.search(body[:600]):
        return None
    j = jparse(body)

    if rec["kind"] == "prm":
        if status == 200 and "json" in ctype and isinstance(j, dict):
            if "authorization_servers" in j or ("resource" in j and len(j) > 1):
                return "prm"
        return None

    if "resource_metadata" in wa:
        return "protected"
    if isinstance(j, dict) and j.get("jsonrpc") == "2.0":
        res = j.get("result")
        if isinstance(res, dict) and ("protocolVersion" in res or "serverInfo" in res):
            return "live"
        if "error" in j:
            return "rpcerror"
    if isinstance(j, dict) and ("protocolVersion" in j or "serverInfo" in j):
        return "live"
    # Stored bodies are truncated at 600 chars, so a long handshake frame cannot be
    # parsed whole. The body is already known not to be HTML, and these two markers
    # only ever appear together in an MCP initialize result.
    if status == 200 and '"protocolVersion"' in body and (
            '"serverInfo"' in body or '"capabilities"' in body):
        return "live"
    # Body is already known not to be HTML here, so text/plain auth errors
    # ("Use: Bearer <paddle-api-key>") count just like JSON ones.
    if status in (401, 403, 400):
        if url.rstrip("/") in DOCSET:
            return "documented"
        return "authwall" if mcp_dedicated(url) else "ambiguous"
    return None


def main():
    ev = defaultdict(lambda: defaultdict(list))
    for path in sys.argv[1:-1]:
        for line in open(path):
            rec = json.loads(line)
            t = tier(rec)
            if t:
                urls = ev[rec["domain"]][t]
                if rec["url"] not in urls:
                    urls.append(rec["url"])

    out = {}
    for d, tiers in ev.items():
        best = next(t for t in ORDER if tiers.get(t))
        out[d] = {"best": best, "evidence": {k: v for k, v in tiers.items()}}
    json.dump(out, open(sys.argv[-1], "w"), indent=1, sort_keys=True)

    counts = defaultdict(int)
    for v in out.values():
        counts[v["best"]] += 1
    print("domains with evidence:", len(out))
    for t in ORDER:
        print(f"  {t:10} {counts[t]}")


if __name__ == "__main__":
    main()
