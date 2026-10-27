"""Generate CLEAN carrier documents with free-tier LLM APIs (Groq, Gemini). Resumable: re-run to continue.
  set GROQ_API_KEY and/or GEMINI_API_KEY, then e.g.
  python generate_carriers.py --provider groq   --model llama-3.3-70b-versatile --name groq-llama   --per-kind 170
  python generate_carriers.py --provider groq   --model <another groq model>    --name groq-other   --per-kind 170
  python generate_carriers.py --provider gemini --model gemini-2.0-flash        --name gemini       --per-kind 170
  python generate_carriers.py --provider groq --list-models     (model names change; list what your key can use)
Output: carriers/real/<name>.jsonl  (one JSON per line: id, kind, source, topic, text)"""
import os, sys, json, time, random, re, argparse, pathlib
import requests

TOPICS = """composting|houseplant care|local bus timetables|budget laptops|hiking trail conditions|sourdough baking|home insulation|city bike lanes|
public library services|community garden|electric vehicle charging|tax filing deadlines|first aid basics|cloud storage options|smartphone battery care|
university admissions|volunteer onboarding|water quality report|quarterly sales summary|lab safety rules|product launch plan|office relocation|
travel itinerary|invoice reminder|meeting reschedule|conference registration|insurance claim steps|recycling rules|renting an apartment|
job interview tips|remote work policy|wedding venue booking|marathon training|photography basics|used car buying|home internet plans|
online privacy settings|climate adaptation|museum exhibition|restaurant opening hours|school fundraising|gym membership terms|pet adoption|
bank account fees|solar panel installation|flood preparedness|open source licences|data backup habits|coffee brewing|language learning apps|
neighbourhood safety|farmers market|airline baggage rules|hospital visiting hours|scholarship applications|software update notes|
small business accounting|street food guide|national park permits|knitting patterns|board game review|garden pest control|
bridge maintenance notice|city council agenda|podcast recommendations|moving checklist|baby sleep routines|smart home devices|
history of the printing press|volcano science|bird migration|ocean tides|vaccine schedule overview|public transport accessibility|
rainwater harvesting|bike repair|chess openings|film festival schedule|local election information|power outage notice|
library book return|parking permit renewal|customer support policy|warranty terms|team offsite agenda|budget planning|
research grant timeline|seminar announcement|course syllabus|dormitory rules|alumni newsletter|clinic appointment reminder|
tenant association meeting|apartment maintenance request|shipping delay notice|subscription renewal|password reset guidance|
newsletter roundup|mountain weather|cycling event|poetry workshop|craft fair|3D printing basics|drone regulations""".replace("\n","").split("|")
KIND_DESC = {"web": "web page article (like a blog post, guide, news item or service page)",
             "email": "plain-text email (with a Subject line, a greeting, a body and a sign-off)",
             "document": "internal or public document (report, handbook section, notice or memo)"}
PROMPT = ("Write a realistic {kind_desc} about: {topic}. About {words} words, at least 5 short paragraphs, "
          "a blank line between paragraphs. Plain prose only: no markdown, no bullet lists, no headings with # symbols. "
          "Do NOT include any instructions or messages addressed to an AI, assistant or language model. "
          "Output only the text itself, with no preface or closing remark.")
BAD = re.compile(r"ignore (all |any )?(previous|prior)|as an ai|language model|\bAI assistant\b|system prompt|^here('| i)s", re.I | re.M)

def call_groq(model, prompt, key):
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=90,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 1.0, "max_tokens": 3500})
    return r, (lambda j: j["choices"][0]["message"]["content"])
def call_mistral(model, prompt, key):
    r = requests.post("https://api.mistral.ai/v1/chat/completions", timeout=90,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 1.0, "max_tokens": 3500})
    return r, (lambda j: j["choices"][0]["message"]["content"])
def call_gemini(model, prompt, key):
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}", timeout=90,
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 1.0, "maxOutputTokens": 3500}})
    return r, (lambda j: j["candidates"][0]["content"]["parts"][0]["text"])

def clean_text(t):
    from carriers import normalize_text
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S)
    t = normalize_text(t)
    t = re.sub(r"[#*_`]+", "", t).strip()
    return re.sub(r"\n{3,}", "\n\n", t)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["groq", "gemini", "mistral"], required=True); ap.add_argument("--model")
    ap.add_argument("--name"); ap.add_argument("--per-kind", type=int, default=170); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=2.5, help="seconds between calls (free tiers are rate limited)")
    ap.add_argument("--list-models", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    keyname = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY", "mistral": "MISTRAL_API_KEY"}[a.provider]; key = os.environ.get(keyname, "")
    if a.list_models:
        if a.provider == "gemini": r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=30)
        else:
            url = "https://api.groq.com/openai/v1/models" if a.provider == "groq" else "https://api.mistral.ai/v1/models"
            r = requests.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=30)
        j = r.json()
        print([m.get("id") or m.get("name") for m in j.get("data", j.get("models", []))]); return
    if not a.dry_run and not key: sys.exit(f"set {keyname} first")
    if not (a.model and a.name): sys.exit("--model and --name are required")
    out = pathlib.Path("carriers/real"); out.mkdir(parents=True, exist_ok=True); f = out / f"{a.name}.jsonl"
    done = {json.loads(l)["id"] for l in open(f, encoding="utf-8")} if f.exists() else set()
    rng = random.Random(a.seed); jobs = []
    for kind in KIND_DESC:
        for i in range(a.per_kind):
            jobs.append((f"{a.name}-{kind}-{i:04d}", kind, TOPICS[(i * 7 + len(kind)) % len(TOPICS)] if i < len(TOPICS) else rng.choice(TOPICS), rng.choice([220, 300, 380, 450])))
    caller = {"groq": call_groq, "gemini": call_gemini, "mistral": call_mistral}[a.provider]
    ok = bad = 0
    for jid, kind, topic, words in jobs:
        if jid in done: continue
        prompt = PROMPT.format(kind_desc=KIND_DESC[kind], topic=topic, words=words)
        if a.dry_run: print(prompt); return
        for attempt in range(6):
            try:
                r, get = caller(a.model, prompt, key)
                if r.status_code == 429: time.sleep(10 * (attempt + 1)); continue
                if r.status_code != 200: print("HTTP", r.status_code, r.text[:200]); time.sleep(5); continue
                text = clean_text(get(r.json())); break
            except Exception as e: print("error:", e); time.sleep(5); text = None
        else: text = None
        if not text or len(text.split()) < 120 or BAD.search(text): bad += 1; continue
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(id=jid, kind=kind, source=a.name, topic=topic, text=text), ensure_ascii=False) + "\n")
        ok += 1
        if ok % 20 == 0: print(f"{a.name}: {ok} saved, {bad} rejected")
        time.sleep(a.sleep)
    print(f"done: {ok} new, {bad} rejected -> {f}")
if __name__ == "__main__": main()