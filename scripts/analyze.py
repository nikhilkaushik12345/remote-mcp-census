"""Re-classify raw probe hits strictly, to kill catch-all/SPA false positives.

A 200 on /.well-known/oauth-protected-resource means nothing on its own: many sites
return index.html with status 200 for any path. Require real parsed JSON with the
RFC 9728 shape. Same for handshakes: require a JSON-RPC envelope, not an HTML page.
"""
import json
import re
import sys
from collections import defaultdict


def jparse(body):
    body = body.strip()
    if not body.startswith(("{", "[")):
        m = re.search(r"^data:\s*(\{.*)$", body, re.M)  # SSE framing
        if not m:
            return None
        body = m.group(1)
    for cut in (len(body), body.rfind("}") + 1):
        try:
            return json.loads(body[:cut])
        except Exception:
            continue
    return None


def strict(rec):
    body, ctype = rec.get("body", "") or "", (rec.get("ctype") or "").lower()
    wa = (rec.get("wa") or "").lower()
    status = rec.get("status")

    if rec["kind"] == "prm":
        if status != 200 or "json" not in ctype:
            return None
        j = jparse(body)
        if not isinstance(j, dict):
            return None
        if "authorization_servers" in j or ("resource" in j and len(j) > 1):
            return "oauth_prm"
        return None

    if "resource_metadata" in wa:
        return "mcp_401"

    j = jparse(body)
    if isinstance(j, dict) and j.get("jsonrpc") == "2.0":
        res = j.get("result")
        if isinstance(res, dict) and ("protocolVersion" in res or "serverInfo" in res):
            return "handshake"
        if "error" in j:
            return "mcp_error"
    return None


def main():
    per = defaultdict(lambda: {"handshake": [], "mcp_401": [], "oauth_prm": [],
                               "mcp_error": [], "raw": []})
    for line in open(sys.argv[1]):
        rec = json.loads(line)
        sig = strict(rec)
        if sig:
            per[rec["domain"]][sig].append(rec["url"])
            per[rec["domain"]]["raw"].append(rec)

    tiers = {"confirmed": [], "weak": []}
    for d, v in sorted(per.items()):
        strong = v["handshake"] or v["mcp_401"] or v["oauth_prm"]
        tiers["confirmed" if strong else "weak"].append(d)

    json.dump({k: {kk: vv for kk, vv in v.items() if kk != "raw"}
               for k, v in per.items()}, open(sys.argv[2], "w"), indent=1)

    print(f"confirmed live MCP domains: {len(tiers['confirmed'])}")
    for d in tiers["confirmed"]:
        v = per[d]
        best = ("handshake" if v["handshake"] else
                "mcp_401" if v["mcp_401"] else "oauth_prm")
        url = (v["handshake"] or v["mcp_401"] or v["oauth_prm"])[0]
        print(f"  {d:28} {best:9} {url}")
    print(f"\nweak/error-only (needs review): {len(tiers['weak'])}")
    for d in tiers["weak"]:
        print(f"  {d:28} {per[d]['mcp_error'][:2]}")


if __name__ == "__main__":
    main()
