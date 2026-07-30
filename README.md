# Remote MCP Server Census

**16,435 verified** · **11,655 OAuth** · **8,358 OAuth root domains**

Live protocol verification only (MCP `initialize` + RFC 9728/8414).

## OAuth re-verification (2026-07-30)
All 11,671 previously OAuth-confirmed hosts rechecked live.
- **99.86% pass** (11,655 still OAuth-ok with live PRM/AS)
- **16 removed** (dead, not MCP-shaped, or OAuth metadata only on non-MCP paths)
- Artifacts: `remote_mcp_oauth_reverified.csv`, `oauth_reverify_failures.csv`, `oauth_reverify_stats.json`

## Files
- `remote_mcp_servers.csv` / `.json` — full verified set
- `remote_mcp_oauth.csv` — OAuth-confirmed hosts
- `remote_mcp_oauth_root_domains.csv` — one host per company root
- `index.html` · `evidence/` · `scripts/`
