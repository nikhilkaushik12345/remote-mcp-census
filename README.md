# Remote MCP Server Census

**11,451 verified** · **6,731 OAuth** · **3,494 OAuth root domains**

Live protocol verification only (MCP `initialize` + RFC 9728/8414).

## Filtered out (platform auth noise)
Removed **4,984** hosts whose authorization is **Shopify** (storefront-renderer / customer-account), **Cloudflare Access**, or **ReadMe** (`dash.readme.com` OIDC) — not first-party product OAuth.
See `removed_platform_auth.csv`.

## Files
- `remote_mcp_servers.csv` / `.json` — full verified set
- `remote_mcp_oauth.csv` — OAuth-confirmed hosts
- `remote_mcp_oauth_root_domains.csv` — one host per company root
- `index.html` · `removed_platform_auth.csv` · `evidence/` · `scripts/`
