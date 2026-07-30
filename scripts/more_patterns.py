"""Wider host/path patterns + sibling TLD guesses for remaining open domains."""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
import urllib3

urllib3.disable_warnings()
sys.path.insert(0, "work")
from http_stage import fetch
from consolidate import tier

# Extra hosts that product MCP often lives on
EXTRA_SUBS = [
    "mcp", "api", "app", "apps", "platform", "cloud", "dev", "developer",
    "developers", "docs", "doc", "help", "support", "learn", "portal",
    "console", "dashboard", "gateway", "agent", "agents", "ai", "studio",
    "connect", "integrations", "partner", "partners", "openapi", "open",
    "stream", "sse", "ws", "rpc", "services", "svc", "edge", "cdn",
]
EXTRA_PATHS = [
    "/mcp", "/v1/mcp", "/v2/mcp", "/api/mcp", "/api/v1/mcp", "/sse",
    "/mcp/sse", "/mcp/", "/messages", "/mcp/messages", "/rpc",
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-protected-resource/mcp",
    "/api/ai/mcp", "/ai/mcp", "/agent/mcp", "/agents/mcp",
]
# Known sibling roots for open brands (corpus domain -> host patterns to try)
SIBLINGS = {
    "1password.com": ["mcp.1password.com", "1password.com", "developer.1password.com",
                      "www.1password.dev", "1password.dev"],
    "audible.com": ["mcp.audible.com", "api.audible.com", "developer.audible.com"],
    "creditkarma.com": ["mcp.creditkarma.com", "anthropic.mcp.creditkarma.com",
                        "api.creditkarma.com"],
    "crowdstrike.com": ["mcp.crowdstrike.com", "api.crowdstrike.com",
                        "falcon.crowdstrike.com", "developer.crowdstrike.com"],
    "discourse.org": ["meta.discourse.org", "discourse.org", "try.discourse.org"],
    "ela.st": ["mcp.elest.io", "elest.io", "cloud.elastic.co", "mcp.elastic.co"],
    "elastic.co": ["mcp.elastic.co", "cloud.elastic.co", "api.elastic.co"],
    "expressvpn.com": ["mcp.expressvpn.com", "api.expressvpn.com"],
    "matomo.org": ["mcp.matomo.org", "api.matomo.cloud", "matomo.cloud"],
    "mattermost.com": ["mcp.mattermost.com", "api.mattermost.com"],
    "okta.com": ["mcp.okta.com", "integrator.okta.com", "dev-mcp.okta.com"],
    "roblox.com": ["mcp.roblox.com", "apis.roblox.com", "create.roblox.com"],
    "sber.ru": ["mcp.sber.ru", "developers.sber.ru", "api.sber.ru"],
    "sendgrid.com": ["mcp.sendgrid.com", "api.sendgrid.com"],
    "skyscanner.net": ["mcp.skyscanner.net", "partners.skyscanner.net",
                       "developers.skyscanner.net"],
    "starkscan.co": ["api.starkscan.co", "mcp.starkscan.co", "starkscan.co"],
    "toobit.com": ["mcp.toobit.com", "api.toobit.com", "api-docs.toobit.com"],
    "unity.com": ["mcp.unity.com", "api.unity.com", "cloud.unity.com",
                  "services.api.unity.com"],
    "unity3d.com": ["mcp.unity3d.com", "services.api.unity.com"],
    "visaacceptance.com": ["mcp.visaacceptance.com", "api.visaacceptance.com",
                           "developer.visaacceptance.com"],
    "whoop.com": ["mcp.whoop.com", "api.whoop.com", "developer.whoop.com"],
    "bitget.com": ["mcp.bitget.com", "api.bitget.com", "www.bitget.com"],
    "blofin.com": ["mcp.blofin.com", "api.blofin.com"],
    "cloud.ru": ["mcp.cloud.ru", "api.cloud.ru"],
    "cobo.com": ["mcp.cobo.com", "api.cobo.com", "api.dev.cobo.com"],
    "hotwire.com": ["mcp.hotwire.com", "api.hotwire.com"],
    "jora.com": ["api.jora.com", "mcp.jora.com"],
    "pinterest.com": ["api.pinterest.com", "mcp.pinterest.com",
                      "developers.pinterest.com"],
    "twitter.com": ["api.twitter.com", "mcp.twitter.com", "api.x.com"],
    "service-now.com": ["mcp.service-now.com"],
    "sgnl.ai": ["mcp.sgnl.ai", "api.sgnl.ai"],
    "trae.ai": ["mcp.trae.ai", "api.trae.ai"],
    "npmjs.org": ["mcp.npmjs.org", "registry.npmjs.org"],
    "backstage.io": ["mcp.backstage.io", "demo.backstage.io"],
    "thalesgroup.com": ["mcp.thalesgroup.com", "api.thalesgroup.com"],
    "hacking-lab.com": ["mcp.hacking-lab.com", "api.hacking-lab.com"],
    "student.monash": ["mcp.monash.edu", "api.monash.edu", "student.monash"],
}


def main():
    rows = json.load(open("work/rows.json"))
    open_d = [r["domain"] for r in rows if r["status"] in ("doc_lead", "review")]
    jobs, seen = [], set()

    def add(d, url, kind="init"):
        if url not in seen:
            seen.add(url)
            jobs.append((d, url, kind))

    for d in open_d:
        for sub in EXTRA_SUBS:
            host = f"{sub}.{d}" if sub else d
            for p in EXTRA_PATHS:
                kind = "prm" if "well-known" in p else "init"
                add(d, f"https://{host}{p}", kind)
        for host in SIBLINGS.get(d, []):
            for p in EXTRA_PATHS:
                kind = "prm" if "well-known" in p else "init"
                add(d, f"https://{host}{p}", kind)

    print(f"domains={len(open_d)} probes={len(jobs)}", flush=True)
    hits = {}
    out = open(sys.argv[1], "w")
    done = 0
    with ThreadPoolExecutor(max_workers=56) as ex:
        for rec in ex.map(fetch, jobs):
            done += 1
            out.write(json.dumps(rec) + "\n")
            t = tier(rec)
            if t and t != "ambiguous":
                # reject HTML
                body = (rec.get("body") or "")[:200].lower()
                if "<html" in body or "<!doctype" in body:
                    continue
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                print(f"  HIT {t:10} {rec['domain']:22} {rec['url']}", flush=True)
            if done % 800 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
    out.close()
    print(f"\ndomains with signal: {len(hits)}")
    for d, v in sorted(hits.items()):
        print(f"  {d:24} {v[0][0]:10} {v[0][1]}")


if __name__ == "__main__":
    main()
