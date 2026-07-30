"""Fast search+probe of remaining open domains."""
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

sys.path.insert(0, "work")
from consolidate import tier
from http_stage import fetch

GW = os.environ["V4_GATEWAY_URL"].rstrip("/")
TOK = os.environ["V4_RUN_TOKEN"]
URL_RE = re.compile(r"https?://[^\s\)\]\"'<>\\]+")
BLOCK = re.compile(
    r"github\.com|npmjs|smithery|glama|pipedream|medium\.com|youtube|"
    r"linkedin\.com|reddit|example\.com|localhost|mintlify\.me|workers\.dev",
    re.I,
)

EXTRA = {
    "audible.com": ["https://mcp.audible.com/mcp", "https://mcp.audible.com/sse"],
    "creditkarma.com": [
        "https://mcp.creditkarma.com/mcp",
        "https://anthropic.mcp.creditkarma.com/mcp",
    ],
    "sendgrid.com": [
        "https://api.sendgrid.com/mcp",
        "https://api.sendgrid.com/v3/mcp",
        "https://api.sendgrid.com/mcp/sse",
    ],
    "bitget.com": [
        "https://api.bitget.com/api/v2/mcp",
        "https://mcp.bitget.com/mcp",
    ],
    "blofin.com": [
        "https://openapi.blofin.com/mcp",
        "https://api.blofin.com/mcp",
    ],
    "okta.com": ["https://mcp.okta.com/mcp", "https://okta.mcp.okta.com/mcp"],
    "roblox.com": [
        "https://apis.roblox.com/cloud/v2/mcp",
        "https://apis.roblox.com/mcp",
    ],
    "unity.com": [
        "https://services.api.unity.com/mcp",
        "https://cloud.unity.com/api/mcp",
    ],
    "crowdstrike.com": [
        "https://api.crowdstrike.com/mcp",
        "https://falcon.crowdstrike.com/mcp",
    ],
    "skyscanner.net": [
        "https://partners.api.skyscanner.net/apiservices/mcp",
        "https://api.skyscanner.net/mcp",
    ],
    "discourse.org": [
        "https://meta.discourse.org/discourse-ai/mcp",
        "https://meta.discourse.org/discourse-ai/mcp/sse",
    ],
    "expressvpn.com": [
        "https://api.expressvpn.com/v1/mcp",
        "https://mcp.expressvpn.com/mcp",
    ],
    "sber.ru": [
        "https://mcp.developers.sber.ru/mcp",
        "https://developers.sber.ru/api/mcp",
    ],
    "toobit.com": ["https://api.toobit.com/mcp", "https://mcp.toobit.com/mcp"],
    "whoop.com": [
        "https://api.prod.whoop.com/developer/mcp",
        "https://api.whoop.com/mcp",
    ],
    "visaacceptance.com": [
        "https://apitest.visaacceptance.com/mcp",
        "https://api.visaacceptance.com/mcp",
    ],
    "mattermost.com": [
        "https://community.mattermost.com/api/v4/mcp",
        "https://mcp.mattermost.com/mcp",
    ],
    "cloud.ru": ["https://mcp.api.cloud.ru/mcp", "https://ai.api.cloud.ru/v1/mcp"],
    "cobo.com": ["https://api.cobo.com/v1/mcp", "https://api.dev.cobo.com/v1/mcp"],
    "starkscan.co": ["https://api.starkscan.co/mcp", "https://starkscan.co/mcp"],
    "pinterest.com": ["https://api.pinterest.com/v5/mcp", "https://api.pinterest.com/mcp"],
    "twitter.com": ["https://api.twitter.com/2/mcp", "https://api.x.com/2/mcp"],
    "hotwire.com": ["https://api.hotwire.com/mcp", "https://www.hotwire.com/api/mcp"],
    "sgnl.ai": ["https://api.sgnl.ai/mcp", "https://mcp.sgnl.ai/mcp"],
    "trae.ai": ["https://api.trae.ai/mcp", "https://mcp.trae.ai/mcp"],
    "opera.com": ["https://api.opera.com/mcp", "https://neon.opera.com/mcp"],
    "service-now.com": ["https://developer.servicenow.com/mcp"],
    "availproject.org": ["https://mcp.availproject.org/mcp"],
    "bingx.com": ["https://open-api.bingx.com/mcp", "https://api.bingx.com/mcp"],
    "kucoin.com": ["https://api.kucoin.com/mcp", "https://mcp.kucoin.com/mcp"],
    "nexo.com": ["https://api.nexo.com/mcp"],
    "phemex.com": ["https://api.phemex.com/mcp"],
    "lastpass.com": ["https://lastpass.com/mcp", "https://api.lastpass.com/mcp"],
    "elementor.com": ["https://my.elementor.com/mcp", "https://api.elementor.com/mcp"],
    "epicgames.com": ["https://api.epicgames.dev/mcp", "https://dev.epicgames.com/mcp"],
    "thalesgroup.com": ["https://api.thalesgroup.com/mcp"],
    "unity3d.com": ["https://services.api.unity.com/mcp"],
    "unrealengine.com": ["https://api.unrealengine.com/mcp"],
    "pangea.cloud": ["https://mcp.aws.pangea.cloud/v1", "https://mcp.pangea.cloud/mcp"],
    "insomnia.rest": ["https://api.insomnia.rest/mcp"],
    "imperva.com": ["https://api.imperva.com/mcp"],
    "bitdefender.com": ["https://cloud.gravityzone.bitdefender.com/mcp"],
    "dell.com": ["https://apigtwb2c.us.dell.com/mcp"],
    "linkedin.com": ["https://api.linkedin.com/mcp"],
}


def search(d):
    brand = d.split(".")[0]
    qs = [
        f'site:{d} MCP server endpoint https mcp OR "streamable http" OR sse',
        f'"{brand}" remote hosted MCP server endpoint url official',
        f"mcp.{d} OR mcp.{brand}.com endpoint",
    ]
    urls = []
    for q in qs:
        for _ in range(2):
            try:
                r = requests.post(
                    f"{GW}/api/v4/search",
                    headers={
                        "Authorization": f"Bearer {TOK}",
                        "Content-Type": "application/json",
                    },
                    json={"query": q, "num_results": 6},
                    timeout=40,
                )
                if r.status_code == 200:
                    urls += URL_RE.findall(r.text)
                    break
            except Exception:
                time.sleep(1)
    clean = []
    for u in urls:
        u = u.rstrip(".,;)\"'`\\")
        clean.append(u)
    return d, list(dict.fromkeys(clean))


def first_party(d, u):
    if BLOCK.search(u):
        return False
    try:
        host = u.split("/")[2].lower()
    except Exception:
        return False
    brand = d.split(".")[0].lower()
    return d in host or host.endswith("." + d) or brand == host.split(".")[0]


def main():
    rows = json.load(open("work/rows.json"))
    open_d = [r["domain"] for r in rows if r["status"] in ("doc_lead", "review")]
    print(f"open {len(open_d)}", flush=True)

    found = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        for d, urls in ex.map(search, open_d):
            fp = [u for u in urls if "mcp" in u.lower() and first_party(d, u)]
            if fp:
                found[d] = fp[:8]
                print(f"  {d:24} {fp[:2]}", flush=True)
    print(f"search hits {len(found)}", flush=True)

    jobs, seen = [], set()

    def add(d, u, kind="init"):
        u = u.split("#")[0]
        if not u.startswith("http"):
            return
        if u not in seen:
            seen.add(u)
            jobs.append((d, u, kind))

    for d, urls in found.items():
        for u in urls:
            if re.search(r"/(mcp|sse)(/|$)|//mcp\.", u, re.I):
                add(d, u)
            try:
                host = u.split("/")[2]
                for p in (
                    "/mcp",
                    "/v1/mcp",
                    "/api/mcp",
                    "/sse",
                    "/.well-known/oauth-protected-resource",
                ):
                    add(
                        d,
                        f"https://{host}{p}",
                        "prm" if "well-known" in p else "init",
                    )
            except Exception:
                pass

    for d, urls in EXTRA.items():
        if d in open_d:
            for u in urls:
                add(d, u)

    print(f"probes {len(jobs)}", flush=True)
    out = open("work/http_fast3.jsonl", "w")
    hits = {}
    with ThreadPoolExecutor(max_workers=40) as ex:
        for rec in ex.map(fetch, jobs):
            out.write(json.dumps(rec) + "\n")
            t = tier(rec)
            if t and t != "ambiguous":
                body = (rec.get("body") or "")[:100].lower()
                if "<html" in body or "<!doctype" in body:
                    continue
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                print(f"HIT {t:10} {rec['domain']:22} {rec['url']}", flush=True)
    out.close()
    print(f"hit domains {len(hits)}")
    for d, v in sorted(hits.items()):
        print(f"  {d:22} {v[0][0]:10} {v[0][1]}")


if __name__ == "__main__":
    main()
