"""Stage 2c: refine. Pass 1 used only /mcp and /sse, so servers on other paths
(Atlassian's /v1/mcp) read as 404, and a bare 401 with no resource_metadata header
(Intercom, Paddle, Razorpay) was discarded even though it proves a server is there.

- Retry every host that gave a non-404 answer across a wider path set.
- Probe endpoint URLs taken from vendor documentation for platforms whose servers
  live on hosts no subdomain guess would find (AWS, Google, DigitalOcean, ...).
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from http_stage import fetch

PATHS = ["/mcp", "/v1/mcp", "/api/mcp", "/mcp/", "/sse", "/v1/sse", "/mcp/sse",
         "/messages", "/mcp/server", "/mcp/mcp"]

# Endpoints stated on vendor-owned documentation pages, keyed by the corpus domain.
DOC_URLS = {
    "atlassian.com": ["https://mcp.atlassian.com/v1/mcp", "https://mcp.atlassian.com/v1/sse"],
    "notion.so": ["https://mcp.notion.com/mcp"],
    "amazonaws.com": ["https://aws-mcp.us-east-1.api.aws/mcp",
                      "https://aws-mcp.eu-central-1.api.aws/mcp"],
    "cloudflare.com": ["https://docs.mcp.cloudflare.com/mcp",
                       "https://bindings.mcp.cloudflare.com/mcp",
                       "https://observability.mcp.cloudflare.com/mcp"],
    "digitalocean.com": ["https://apps.mcp.digitalocean.com/mcp",
                         "https://droplets.mcp.digitalocean.com/mcp",
                         "https://docs.mcp.digitalocean.com/mcp"],
    "googleapis.com": ["https://bigquery.googleapis.com/mcp",
                       "https://run.googleapis.com/mcp",
                       "https://compute.googleapis.com/mcp"],
    "salesforce.com": ["https://api.salesforce.com/platform/mcp/v1/mcp"],
    "plaid.com": ["https://api.dashboard.plaid.com/mcp/"],
    "newrelic.com": ["https://mcp.eu.newrelic.com/mcp/"],
    "intercom.com": ["https://mcp.eu.intercom.com/mcp"],
    "paddle.com": ["https://mcp.sandbox.paddle.com/mcp"],
    "gitlab.com": ["https://gitlab.com/api/v4/mcp", "https://gitlab.com/api/v4/orbit/mcp"],
    "quizlet.com": ["https://api.quizlet.com/v4/partner/v1/mcp"],
    "shopify.com": ["https://shopify.com/api/mcp"],
    "myshopify.com": ["https://shop.app/api/mcp"],
    "hostinger.com": ["https://mcp.hostinger.com/mcp"],
    "optimizely.com": ["https://exp.mcp.opal.optimizely.com/mcp",
                       "https://analytics.mcp.opal.optimizely.com/mcp"],
    "databricks.com": ["https://api.databricks.com/api/2.0/mcp/functions"],
    "square.online": ["https://mcp.squareup.com/mcp"],
}


def interesting_hosts(probe_file):
    """Hosts that answered something other than a plain 404/connection error."""
    hosts = {}
    for line in open(probe_file):
        r = json.loads(line)
        st = r.get("status")
        if st is None or st == 404:
            continue
        host = r["url"].split("/")[2]
        if host.startswith("mcp.") or host.startswith("api.") or ".mcp." in host:
            hosts.setdefault(host, r["domain"])
    return hosts


def main():
    hosts = interesting_hosts(sys.argv[1])
    jobs = [(dom, f"https://{h}{p}", "init") for h, dom in hosts.items() for p in PATHS]
    jobs += [(d, u, "init") for d, urls in DOC_URLS.items() for u in urls]
    seen, uniq = set(), []
    for j in jobs:
        if j[1] not in seen:
            seen.add(j[1])
            uniq.append(j)
    print(f"hosts={len(hosts)} probes={len(uniq)}", flush=True)
    out = open(sys.argv[2], "w")
    done = 0
    with ThreadPoolExecutor(max_workers=48) as ex:
        for rec in ex.map(fetch, uniq):
            done += 1
            st = rec.get("status")
            if rec["signal"] or st in (401, 403, 400, 405, 406, 200):
                out.write(json.dumps(rec) + "\n")
            if done % 400 == 0:
                print(f"  {done}/{len(uniq)}", flush=True)
    out.close()
    print("done")


if __name__ == "__main__":
    main()
