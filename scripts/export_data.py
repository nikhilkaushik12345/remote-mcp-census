"""Write the machine-readable deliverables that ship alongside the HTML report."""
import csv
import json
import os

rows = json.load(open("work/rows.json"))
oauth = json.load(open("work/oauth.json"))
os.makedirs("outputs/data", exist_ok=True)

FULL = "outputs/data/all_3186_domains.csv"
CONF = "outputs/data/confirmed_mcp_servers.csv"

with open(FULL, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["domain", "organisation", "status", "evidence_tier", "endpoints",
                "server_name", "server_kind", "oauth", "open_dcr", "pkce",
                "auth_note", "oauth_issuer", "scopes", "doc_url", "platform_note"])
    for r in rows:
        w.writerow([r["domain"], r["name"], r["status"], r["tier"],
                    " | ".join(r["endpoints"]), r["server"], r["kind"],
                    "yes" if r["oauth"] else "no",
                    "yes" if r["dcr"] else ("no" if r["oauth"] else ""),
                    "yes" if r["pkce"] else ("no" if r["oauth"] else ""),
                    r["auth_note"], r["issuer"], " ".join(r["scopes"]),
                    r["doc"] or "", r["platform"]])

conf = [r for r in rows if r["status"] == "confirmed"]
with open(CONF, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["domain", "organisation", "endpoint", "evidence_tier", "server_name",
                "server_kind", "oauth", "open_dcr", "pkce", "oauth_issuer",
                "scopes", "auth_note", "doc_url"])
    for r in sorted(conf, key=lambda r: r["domain"]):
        w.writerow([r["domain"], r["name"],
                    r["endpoints"][0] if r["endpoints"] else "", r["tier"],
                    r["server"], r["kind"], "yes" if r["oauth"] else "no",
                    "yes" if r["dcr"] else "", "yes" if r["pkce"] else "",
                    r["issuer"], " ".join(r["scopes"]), r["auth_note"], r["doc"] or ""])

json.dump({"confirmed": [
    {k: r[k] for k in ("domain", "name", "tier", "endpoints", "server", "kind",
                       "oauth", "dcr", "pkce", "scopes", "issuer", "auth_note", "doc")}
    for r in sorted(conf, key=lambda r: r["domain"])]},
    open("outputs/data/confirmed_mcp_servers.json", "w"), indent=1)
json.dump(oauth, open("outputs/data/oauth_details.json", "w"), indent=1)

n_oauth = sum(1 for r in conf if r["oauth"])
print(f"wrote {FULL} ({len(rows)} rows)")
print(f"wrote {CONF} ({len(conf)} rows, {n_oauth} with OAuth)")
