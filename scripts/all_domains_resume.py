"""Resume all_domains_sweep from where http_all.jsonl left off."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "work")
from http_stage import fetch
from consolidate import tier
from all_domains_sweep import urls_for


def main():
    rows = json.load(open("work/rows.json"))
    doh = json.load(open("work/doh.json"))
    done_urls = set()
    for line in open("work/http_all.jsonl"):
        try:
            done_urls.add(json.loads(line)["url"])
        except Exception:
            pass

    targets = []
    for r in rows:
        st, d = r["status"], r["domain"]
        if st in ("confirmed", "no_dns"):
            continue
        if st in ("doc_lead", "review", "inconclusive"):
            targets.append(d)
            continue
        hosts = doh.get(d, {}).get("hosts", {})
        if hosts.get(d) or hosts.get(f"mcp.{d}") or hosts.get(f"api.{d}") or hosts.get(d) is None:
            targets.append(d)
    targets = list(dict.fromkeys(targets))

    jobs = []
    for d in targets:
        for j in urls_for(d):
            if j[1] not in done_urls:
                jobs.append(j)
    print(f"remaining probes={len(jobs)} already={len(done_urls)}", flush=True)

    out = open(sys.argv[1], "a", buffering=1)
    hits, done = {}, 0
    with ThreadPoolExecutor(max_workers=64) as ex:
        for rec in ex.map(fetch, jobs):
            done += 1
            try:
                out.write(json.dumps(rec) + "\n")
            except Exception as e:
                print("write err", e, flush=True)
                break
            t = tier(rec)
            if t and t != "ambiguous":
                body = (rec.get("body") or "")[:120].lower()
                if "<html" in body or "<!doctype" in body or "captcha" in body:
                    continue
                hits.setdefault(rec["domain"], []).append((t, rec["url"]))
                print(f"  HIT {t:10} {rec['domain']:28} {rec['url']}", flush=True)
            if done % 1500 == 0:
                print(f"  {done}/{len(jobs)} new_hit_domains={len(hits)}", flush=True)
    out.close()
    print(f"resume done probes={done} new_domains={len(hits)}")
    for d, v in sorted(hits.items()):
        print(f"  {d:28} {v[0][0]:10} {v[0][1]}")


if __name__ == "__main__":
    main()
