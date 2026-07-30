"""Disambiguate 401/403 answers on general API hosts with a control path.

If https://host/<nonsense> answers exactly like https://host/mcp, the status is a
blanket WAF/auth response and says nothing about MCP. If the control 404s while /mcp
returns 401, the /mcp route genuinely exists.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from http_stage import fetch

CONTROL = "zz-control-not-a-route-8471"


def main():
    ev = json.load(open(sys.argv[1]))
    targets = []
    for d, rec in ev.items():
        if rec["best"] != "ambiguous":
            continue
        for url in rec["evidence"].get("ambiguous", []):
            host = url.split("/")[2]
            targets.append((d, url, f"https://{host}/{CONTROL}"))

    jobs = [(d, c, "init") for d, _, c in targets]
    seen, uniq = set(), []
    for j in jobs:
        if j[1] not in seen:
            seen.add(j[1])
            uniq.append(j)
    print(f"controls: {len(uniq)}", flush=True)

    res = {}
    with ThreadPoolExecutor(max_workers=40) as ex:
        for rec in ex.map(fetch, uniq):
            res[rec["url"]] = rec.get("status")

    verdict = {}
    for d, url, ctrl in targets:
        real = json.loads(json.dumps(url))
        cs = res.get(ctrl)
        verdict.setdefault(d, []).append({"url": real, "control_status": cs})
    json.dump(verdict, open(sys.argv[2], "w"), indent=1)

    keep, drop = [], []
    for d, items in verdict.items():
        # /mcp is real if some control 404s (route-specific auth) rather than mirroring
        if any(i["control_status"] in (404, 400) for i in items):
            keep.append(d)
        else:
            drop.append(d)
    print(f"route-specific (keep): {len(keep)}")
    print("  " + ", ".join(sorted(keep)))
    print(f"blanket block (drop): {len(drop)}")


if __name__ == "__main__":
    main()
