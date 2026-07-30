"""Stage 1 (v2): resolve MCP-candidate hosts over DoH, with wildcard-DNS detection.

Local resolver gave false negatives; DoH (Cloudflare, Google fallback) is authoritative
and rate-stable. A wildcard canary marks domains where mcp.<d> resolving proves nothing.
"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

SUBS = ["", "mcp", "api", "docs"]
CANARY = "zz-no-such-host-probe9137"
RESOLVERS = [
    ("https://cloudflare-dns.com/dns-query", {"accept": "application/dns-json"}),
    ("https://dns.google/resolve", {"accept": "application/json"}),
]
_local = threading.local()


def sess():
    if not hasattr(_local, "s"):
        s = requests.Session()
        s.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=8, max_retries=0))
        _local.s = s
    return _local.s


def resolves(host):
    """True/False, or None if both resolvers failed to answer."""
    for url, hdrs in RESOLVERS:
        for _ in range(2):
            try:
                r = sess().get(url, params={"name": host, "type": "A"},
                               headers=hdrs, timeout=8)
                if r.status_code != 200:
                    continue
                j = r.json()
                if j.get("Status") == 3:  # NXDOMAIN
                    return False
                if j.get("Status") != 0:
                    continue
                answers = j.get("Answer") or []
                return any(a.get("type") in (1, 5) for a in answers)
            except Exception:
                continue
    return None


def load_domains(path):
    out, seen = [], set()
    for line in open(path, encoding="utf-8", errors="replace"):
        d = line.strip().lower()
        if not d or d.startswith("step 1") or " " in d:
            continue
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def probe(domain):
    rec = {"hosts": {}, "wildcard": None}
    for sub in SUBS:
        host = f"{sub}.{domain}" if sub else domain
        rec["hosts"][host] = resolves(host)
    rec["wildcard"] = resolves(f"{CANARY}.{domain}")
    return domain, rec


def main():
    domains = load_domains(sys.argv[1])
    print(f"domains: {len(domains)}", flush=True)
    out, done = {}, 0
    with ThreadPoolExecutor(max_workers=64) as ex:
        for domain, rec in ex.map(probe, domains):
            out[domain] = rec
            done += 1
            if done % 400 == 0:
                print(f"  {done}/{len(domains)}", flush=True)
    json.dump(out, open(sys.argv[2], "w"))
    roots = sum(1 for v in out.values() if v["hosts"].get(list(v["hosts"])[0]))
    wild = sum(1 for v in out.values() if v["wildcard"])
    mcp = sum(1 for d, v in out.items() if v["hosts"].get(f"mcp.{d}") and not v["wildcard"])
    print(f"root resolves: {roots}  wildcard domains: {wild}  real mcp.* hosts: {mcp}")


if __name__ == "__main__":
    main()
