"""Determine the auth model of every confirmed MCP endpoint.

Chain: endpoint -> RFC 9728 protected-resource metadata -> authorization server
metadata. Records whether OAuth is used, whether Dynamic Client Registration is
open (RFC 7591), whether PKCE is advertised, and the scopes on offer. An endpoint
that only accepts a static API key is recorded as such, not as OAuth.
"""
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
import urllib3

urllib3.disable_warnings()

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "mcp-audit", "version": "1.0"}}}
UA = {"user-agent": "Mozilla/5.0 (compatible; mcp-audit/1.0)"}
_l = threading.local()


def sess():
    if not hasattr(_l, "s"):
        s = requests.Session()
        s.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=4, max_retries=0))
        _l.s = s
    return _l.s


def getj(url):
    try:
        r = sess().get(url, headers={"accept": "application/json", **UA},
                       timeout=12, verify=False, allow_redirects=True)
        if r.status_code != 200 or "json" not in (r.headers.get("content-type") or "").lower():
            return None
        return r.json()
    except Exception:
        return None


def prm_candidates(ep):
    u = urlparse(ep)
    base, path = f"{u.scheme}://{u.netloc}", u.path.rstrip("/")
    out = [f"{base}/.well-known/oauth-protected-resource"]
    if path:
        out.insert(0, f"{base}/.well-known/oauth-protected-resource{path}")
    return out


def as_metadata(issuer):
    iss = issuer.rstrip("/")
    u = urlparse(iss)
    base, path = f"{u.scheme}://{u.netloc}", u.path.rstrip("/")
    urls = [f"{iss}/.well-known/oauth-authorization-server",
            f"{iss}/.well-known/openid-configuration"]
    if path:
        urls += [f"{base}/.well-known/oauth-authorization-server{path}",
                 f"{base}/.well-known/openid-configuration{path}"]
    for u2 in urls:
        j = getj(u2)
        if isinstance(j, dict) and ("authorization_endpoint" in j or "token_endpoint" in j):
            return u2, j
    return None, None


def probe_wa(ep):
    try:
        r = sess().post(ep, json=INIT, timeout=12, verify=False,
                        headers={"content-type": "application/json",
                                 "accept": "application/json, text/event-stream", **UA})
        return r.status_code, (r.headers.get("www-authenticate") or ""), r.text[:400]
    except Exception:
        return None, "", ""


def analyse(row):
    ep = row["endpoints"][0] if row["endpoints"] else None
    res = {"domain": row["domain"], "endpoint": ep, "oauth": False, "dcr": None,
           "pkce": None, "scopes": [], "issuer": None, "as_url": None,
           "auth_note": "", "prm_url": None}
    if not ep:
        return res
    status, wa, body = probe_wa(ep)
    m = re.search(r'resource_metadata="?([^",\s]+)', wa or "")
    prms = ([m.group(1)] if m else []) + prm_candidates(ep)
    prm = None
    for u in prms:
        j = getj(u)
        if isinstance(j, dict) and ("authorization_servers" in j or "resource" in j):
            prm, res["prm_url"] = j, u
            break
    if prm:
        res["oauth"] = True
        res["scopes"] = prm.get("scopes_supported") or []
        servers = prm.get("authorization_servers") or []
        if servers:
            res["issuer"] = servers[0]
            as_url, meta = as_metadata(servers[0])
            if meta:
                res["as_url"] = as_url
                res["dcr"] = bool(meta.get("registration_endpoint"))
                res["pkce"] = meta.get("code_challenge_methods_supported") or None
                if not res["scopes"]:
                    res["scopes"] = meta.get("scopes_supported") or []
    if not res["oauth"]:
        low = (wa + " " + body).lower()
        if "bearer" in low and ("api-key" in low or "api key" in low or "token" in low):
            res["auth_note"] = "static API key / bearer token"
        elif "jwt" in low:
            res["auth_note"] = "JWT credential"
        elif status == 200:
            res["auth_note"] = "no auth required"
        else:
            res["auth_note"] = f"auth unclear (HTTP {status})"
    return res


def main():
    rows = json.load(open("work/rows.json"))
    targets = [r for r in rows if r["status"] in ("confirmed", "review")]
    print(f"analysing auth for {len(targets)} endpoints", flush=True)
    out, done = {}, 0
    with ThreadPoolExecutor(max_workers=20) as ex:
        for res in ex.map(analyse, targets):
            out[res["domain"]] = res
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(targets)}", flush=True)
    json.dump(out, open("work/oauth.json", "w"), indent=1)
    n_oauth = sum(1 for v in out.values() if v["oauth"])
    n_dcr = sum(1 for v in out.values() if v["dcr"])
    n_pkce = sum(1 for v in out.values() if v["pkce"])
    print(f"OAuth: {n_oauth}/{len(out)}   open DCR: {n_dcr}   PKCE advertised: {n_pkce}")


if __name__ == "__main__":
    main()
