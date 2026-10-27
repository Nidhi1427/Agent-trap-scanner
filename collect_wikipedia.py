"""Human-written carriers from Wikipedia (CC BY-SA - cite in the datasheet). Resumable (skips pages already saved).
  python collect_wikipedia.py --n 500 --contact your_email@example.com
One request at a time, honouring Retry-After, because Wikipedia rate-limits fast clients.
Full-text extracts come one page per request, so we pick random page ids and fetch each."""
import json, re, time, argparse, pathlib, requests
API = "https://en.wikipedia.org/w/api.php"
S = requests.Session()

def get_json(params, tries=6):
    for i in range(tries):
        try:
            r = S.get(API, params=dict(params, maxlag=5), timeout=30)
        except Exception as e:
            print("network error:", e); time.sleep(5 * (i + 1)); continue
        if r.status_code in (429, 503):
            wait = int(r.headers.get("Retry-After", 15 * (i + 1)) or 15); print(f"HTTP {r.status_code}: waiting {wait}s"); time.sleep(min(wait, 120)); continue
        try:
            j = r.json()
        except Exception:
            print(f"HTTP {r.status_code}, not JSON: {r.text[:100]!r}"); time.sleep(10 * (i + 1)); continue
        if "error" in j and j["error"].get("code") == "maxlag": time.sleep(5); continue
        return j
    return None

def random_pages(k=20):
    j = get_json(dict(action="query", format="json", list="random", rnnamespace=0, rnlimit=k))
    return [(p["id"], p["title"]) for p in j["query"]["random"]] if j else []

def fetch(page):
    pid, title = page
    j = get_json(dict(action="query", format="json", prop="extracts", explaintext=1, exlimit=1, pageids=pid))
    try: ext = j["query"]["pages"][str(pid)].get("extract", "")
    except Exception: return None
    ext = re.sub(r"\n==+[^=\n]+==+\n", "\n\n", ext); ext = re.sub(r"\n{3,}", "\n\n", ext).strip()
    paras = [x.strip() for x in ext.split("\n\n") if len(x.split()) >= 25][:8]
    text = "\n\n".join(paras)
    if len(paras) < 3 or not (120 <= len(text.split()) <= 800): return None
    return dict(id=f"wiki-{pid}", kind="web", source="wikipedia-human", topic=title, text=text)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--contact", default="student-project", help="your email, so Wikipedia can contact you (recommended)")
    ap.add_argument("--pause", type=float, default=1.2); a = ap.parse_args()
    S.headers["User-Agent"] = f"CPI-AgentTrapScanner/0.3 (student research project; {a.contact})"
    f = pathlib.Path("carriers/real/wikipedia.jsonl"); f.parent.mkdir(parents=True, exist_ok=True)
    seen = {json.loads(l)["id"] for l in open(f, encoding="utf-8")} if f.exists() else set()
    n, empty = len(seen), 0
    print(f"starting with {n} saved, target {a.n}")
    while n < a.n and empty < 15:
        pages = random_pages(20); got = 0
        if not pages: empty += 1; time.sleep(20); continue
        for pg in pages:
            rec = fetch(pg); time.sleep(a.pause)
            if rec and rec["id"] not in seen:
                with open(f, "a", encoding="utf-8") as fh: fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                seen.add(rec["id"]); n += 1; got += 1
                if n >= a.n: break
        empty = 0 if got else empty + 1
        print(f"{n} saved (+{got})")
    print("done" if n >= a.n else "stopped: too many empty rounds")