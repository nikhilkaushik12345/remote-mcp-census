"""Pull serverInfo.name out of every successful handshake.

This separates a vendor's product MCP server from a documentation-platform server
(Mintlify/ReadMe auto-mount one at docs.<vendor>/mcp). Both are genuinely
vendor-hosted, but they are not the same claim, so the report labels them.
"""
import json
import re

FILES = ["work/http.jsonl", "work/http2.jsonl", "work/http3.jsonl",
         "work/http4.jsonl", "work/http5.jsonl", "work/http6.jsonl", "work/http7.jsonl", "work/http10.jsonl", "work/http10b.jsonl", "work/http_more_clean.jsonl", "work/http_all_clean.jsonl", "work/http_fast_clean.jsonl",
         "work/http8_verified.jsonl"]
DOCS_HINT = re.compile(r"mintlify|readme\.?io|docs|documentation|gitbook", re.I)


def jparse(body):
    b = (body or "").strip()
    if not b.startswith(("{", "[")):
        m = re.search(r"^data:\s*(\{.*)$", b, re.M)
        if not m:
            return None
        b = m.group(1)
    for cut in (len(b), b.rfind("}") + 1):
        try:
            return json.loads(b[:cut])
        except Exception:
            continue
    return None


def main():
    out = {}
    for f in FILES:
        try:
            fh = open(f)
        except FileNotFoundError:
            continue
        for line in fh:
            r = json.loads(line)
            j = jparse(r.get("body"))
            if not isinstance(j, dict):
                continue
            res = j.get("result") if isinstance(j.get("result"), dict) else j
            si = res.get("serverInfo") if isinstance(res, dict) else None
            if not isinstance(si, dict):
                continue
            name = (si.get("name") or "").strip()
            if not name:
                continue
            ver = (si.get("version") or "").strip()
            instr = (res.get("instructions") or "")[:200]
            rec = out.setdefault(r["domain"], {})
            rec[r["url"]] = {"name": name, "version": ver,
                             "docs_server": bool(DOCS_HINT.search(name + " " + instr)
                                                 or "/docs" in r["url"]
                                                 or r["url"].split("/")[2].startswith(
                                                     ("docs.", "developer.", "developers.",
                                                      "dev.", "api-portal."))),
                             "instructions": instr}
    json.dump(out, open("work/server_names.json", "w"), indent=1)
    n = sum(len(v) for v in out.values())
    docs = sum(1 for v in out.values() for x in v.values() if x["docs_server"])
    print(f"handshakes with serverInfo: {n} across {len(out)} domains; docs-platform: {docs}")
    for d, v in sorted(out.items())[:18]:
        for u, x in list(v.items())[:1]:
            print(f"  {d:22} {x['name'][:38]:38} {'DOCS' if x['docs_server'] else 'PRODUCT'}")


if __name__ == "__main__":
    main()
