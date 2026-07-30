"""Stage 1: DNS-resolve MCP-candidate hostnames for every root domain."""
import json
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

SUBS = ["mcp", "api", "docs", ""]  # "" = the bare root domain


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


def resolvable(host):
    try:
        socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        return True
    except Exception:
        return False


def probe(domain):
    hits = []
    for sub in SUBS:
        host = f"{sub}.{domain}" if sub else domain
        if resolvable(host):
            hits.append(host)
    return domain, hits


def main():
    domains = load_domains(sys.argv[1])
    print(f"domains: {len(domains)}", flush=True)
    socket.setdefaulttimeout(6)
    results = {}
    done = 0
    with ThreadPoolExecutor(max_workers=120) as ex:
        for domain, hits in ex.map(probe, domains):
            results[domain] = hits
            done += 1
            if done % 250 == 0:
                print(f"  {done}/{len(domains)}", flush=True)
    with open(sys.argv[2], "w") as fh:
        json.dump(results, fh)
    mcp_hosts = sum(1 for v in results.values() if any(h.startswith("mcp.") for h in v))
    print(f"done. domains with mcp.* host: {mcp_hosts}")
    print(f"total candidate hosts: {sum(len(v) for v in results.values())}")


if __name__ == "__main__":
    main()
