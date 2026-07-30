"""Assign every one of the 3,186 corpus domains a final, reconciled status."""
import json
import re
from collections import Counter, defaultdict

CORPUS = "uploads/step1_cleaned_root_domains.txt"
HTMLISH = re.compile(r"<!doctype|<html|captcha|just a moment", re.I)

# ambiguous domains whose /mcp route proved route-specific under the control test
REVIEW_STRONG = ["pinterest.com", "twitter.com", "x.com", "starkscan.co",
                 "komoju.com", "jora.com"]
VERIFIED_LEADS = {"starkscan.co": "authwall", "timeweb.cloud": "authwall"}  # control: /mcp 401, control 404
VERIFIED_ENDPOINTS = {
    "expedia.com": ["https://www.expedia.com/mcp"],
}
REVIEW_WEAK = ["hotwire.com", "hacking-lab.com", "student.monash", "yelp.com"]

NAMES = {
    "amazonaws.com": "Amazon Web Services", "amazon.com": "Amazon Web Services",
    "googleapis.com": "Google Cloud", "google.com": "Google Cloud",
    "notion.so": "Notion", "netlify.app": "Netlify", "neon.tech": "Neon",
    "squareup.com": "Square", "frontapp.com": "Front", "snooguts.net": "Reddit",
    "trello.services": "Trello (Atlassian)", "myshopify.com": "Shopify",
    "shop.app": "Shopify (Shop)", "s-cloud.fi": "S Group", "8x8.studio": "8x8",
    "internetcomputer.org": "Internet Computer / DFINITY",
    "gocardless-staging.io": "GoCardless (staging)", "ean.com": "Expedia (EAN)",
    "cmtelecom.com": "CM.com", "getmoneytree.com": "Moneytree",
    "redoxengine.com": "Redox", "rapyd.org": "Rapyd", "bykea.store": "Bykea",
    "wyzecam.com": "Wyze", "withings.net": "Withings", "vkvideo.ru": "VK",
    "unreal-agents.com": "Unreal Agents", "urbancompany.com": "Urban Company",
    "xadsacademy.com": "xAds Academy", "workbox.dk": "Workbox",
    "logitechclub.com": "Logitech (store)", "redelcom.cl": "Redelcom",
    "decathlon.com": "Decathlon", "canva.cn": "Canva (China)",
}
# platform-operated storefront MCP rather than a vendor-built server
SHOPIFY_STOREFRONT = {"bykea.store", "decathlon.com", "logitechclub.com",
                      "redelcom.cl", "wyze.com", "wyzecam.com",
                      "withings.com", "withings.net"}
UCP_STOREFRONT = {"cybersource.com", "octopus.com", "pantheon.io"}
TIER_LABEL = {
    "live": "Live handshake", "prm": "OAuth resource metadata",
    "protected": "401 + resource_metadata", "authwall": "Auth wall on MCP host",
    "rpcerror": "JSON-RPC error reply",
    "documented": "Documented endpoint, auth-gated",
}


def load_corpus():
    out, seen = [], set()
    for line in open(CORPUS, encoding="utf-8", errors="replace"):
        d = line.strip().lower()
        if not d or d.startswith("step 1") or " " in d:
            continue
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def main():
    corpus = load_corpus()
    ev = json.load(open("work/evidence.json"))
    doh = json.load(open("work/doh.json"))
    docs = json.load(open("work/docs.json"))
    snames = json.load(open("work/server_names.json"))
    leads = json.load(open("work/search_leads.json"))
    try:
        oauth = json.load(open("work/oauth.json"))
    except FileNotFoundError:
        oauth = {}

    probes = defaultdict(list)
    for f in ("work/http.jsonl", "work/http2.jsonl", "work/http3.jsonl",
              "work/http4.jsonl", "work/http5.jsonl", "work/http6.jsonl", "work/http7.jsonl", "work/http10.jsonl", "work/http10b.jsonl", "work/http_more_clean.jsonl", "work/http_all_clean.jsonl", "work/http_fast_clean.jsonl",
              "work/http8_verified.jsonl"):
        for line in open(f):
            r = json.loads(line)
            probes[r["domain"]].append(r)

    rows = []
    for d in corpus:
        e = ev.get(d, {})
        best = e.get("best")
        recs = probes.get(d, [])
        hosts = doh.get(d, {}).get("hosts", {})
        n_probe = len(recs)
        answered = [r for r in recs if r.get("status") is not None]

        if best in TIER_LABEL:
            status, tier = "confirmed", best
        elif d in VERIFIED_LEADS:
            status, tier = "confirmed", VERIFIED_LEADS[d]
        elif d in REVIEW_STRONG:
            status, tier = "review", "route-specific auth"
        elif d in REVIEW_WEAK:
            status, tier = "review", "blocked / unclear"
        elif d in leads:
            status, tier = "doc_lead", ""
        elif not any(hosts.values()) and hosts.get(d) is False:
            status, tier = "no_dns", ""
        elif n_probe and not answered:
            status, tier = "inconclusive", "network unreachable"
        else:
            status, tier = "none", ""

        urls = []
        for t in ("live", "prm", "protected", "documented", "authwall", "rpcerror"):
            urls += e.get("evidence", {}).get(t, [])
        if not urls and d in VERIFIED_LEADS:   # promoted by control/doc evidence
            urls = (VERIFIED_ENDPOINTS.get(d) or
                    e.get("evidence", {}).get("ambiguous", []))
        endpoints = [u for u in dict.fromkeys(urls)
                     if "/.well-known/" not in u] or [u for u in dict.fromkeys(urls)]

        dd = docs.get(d, {})
        doc = next((u for u in dd.get("first_party", []) if re.search(r"mcp", u, re.I)),
                   (dd.get("first_party") or [None])[0])

        sn = snames.get(d, {})
        prod = [v for v in sn.values() if not v["docs_server"]]
        docsrv = [v for v in sn.values() if v["docs_server"]]
        srv_name = (prod or docsrv or [{}])[0].get("name", "")
        kind = ("docs-platform server" if docsrv and not prod else "")
        oa = oauth.get(d, {})

        rows.append({
            "server": srv_name,
            "kind": kind,
            "oauth": bool(oa.get("oauth")),
            "dcr": oa.get("dcr"),
            "pkce": bool(oa.get("pkce")),
            "scopes": (oa.get("scopes") or [])[:6],
            "issuer": oa.get("issuer") or "",
            "auth_note": oa.get("auth_note", ""),
            "leads": leads.get(d, [])[:3],
            "domain": d,
            "name": NAMES.get(d, d.split(".")[0].replace("-", " ").title()),
            "status": status,
            "tier": tier,
            "tier_label": TIER_LABEL.get(tier, tier),
            "endpoints": endpoints[:6],
            "doc": doc,
            "platform": ("Shopify storefront MCP" if d in SHOPIFY_STOREFRONT else
                         "Storefront UCP endpoint" if d in UCP_STOREFRONT else ""),
            "probes": n_probe,
        })

    c = Counter(r["status"] for r in rows)
    print("total rows:", len(rows))
    for k, v in c.most_common():
        print(f"  {k:13} {v}")
    assert len(rows) == 3186, len(rows)
    tc = Counter(r["tier"] for r in rows if r["status"] == "confirmed")
    print("confirmed by tier:", dict(tc))
    json.dump(rows, open("work/rows.json", "w"), indent=1)
    print("total probe requests:", sum(len(v) for v in probes.values()))


if __name__ == "__main__":
    main()
