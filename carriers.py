"""Clean carrier text. Real carriers (LLM-generated pages from >=3 LLMs) go in carriers/real/*.jsonl:
   {"id","kind":"web|email|document","source":"<llm name or human>","html"|"text": ...}
make_toy_carriers() is ONLY for testing the pipeline: numbers measured on it mean nothing."""
import json, random, glob, pathlib
HERE = pathlib.Path(__file__).parent

TOPICS = {
 "web": ["a local bakery's seasonal menu", "a guide to repotting houseplants", "a city bus timetable update",
         "a review of budget laptops", "a primer on home composting", "a hiking trail conditions report"],
 "email": ["a team meeting reschedule", "an invoice reminder", "a conference travel itinerary",
           "a project status update", "a library book return notice"],
 "document": ["a quarterly sales summary", "a research lab safety procedure", "a product requirements overview",
              "a volunteer onboarding handbook", "a municipal water report"],
}
SENT = ["The schedule has been updated to reflect the changes announced last week.",
 "Most people find the process straightforward once the first step is complete.",
 "Prices vary by region and are reviewed every quarter.", "Please see the attached summary for details.",
 "Several readers asked about alternatives, so we have listed three below.",
 "Results were consistent across the sample, with minor variation by season.",
 "The team met on Tuesday to review open items and agree next steps.",
 "Access to the building requires a visitor badge, available at reception.",
 "Overall, the numbers are in line with expectations for this time of year.",
 "We recommend checking the latest notice before making any plans.",
 "A short FAQ follows for anyone who wants more background.",
 "Feedback from the pilot group was largely positive."]
# hard negatives: benign imperatives / benign hidden content that a naive detector would flag
BENIGN_INSTR = ["Please ignore this reminder if you have already paid.", "Click the link below to reset your password.",
 "Do not reply to this message; the mailbox is not monitored.", "Remember to bring your ID to the front desk.",
 "Summarize your changes in the commit message before submitting.", "Follow the steps above in order."]

def make_toy_carriers(n=600, seed=1):
    rng = random.Random(seed); out = []
    for i in range(n):
        kind = rng.choice(list(TOPICS)); topic = rng.choice(TOPICS[kind])
        sents = [rng.choice(SENT) for _ in range(rng.randint(8, 16))]
        hard = rng.random() < 0.25
        if hard: sents.insert(rng.randrange(len(sents)+1), rng.choice(BENIGN_INSTR))
        out.append(dict(id=f"toy{i:05d}", kind=kind, source="toy", topic=topic, sentences=sents, hard_negative=hard))
    return out

def load_bipia(n_table=300, seed=2):
    """Real emails (100) and Wikipedia-style tables from BIPIA (MIT). WebQA/Summarization contexts need NewsQA/arXiv downloads (skipped)."""
    import re
    base = HERE / "raw/BIPIA/benchmark"
    if not base.exists(): return []
    rng = random.Random(seed); out = []
    for split in ("train", "test"):
        for i, l in enumerate(open(base / f"email/{split}.jsonl", encoding="utf-8")):
            ctx = json.loads(l)["context"].replace("|CONTENT:", "\nCONTENT:").replace("|", "\n")
            out.append(dict(id=f"bipia-email-{split}{i:03d}", kind="email", source="BIPIA-email", split_mode="sentence", text=normalize_text(ctx)))
    rows = [json.loads(l) for l in open(base / "table/train.jsonl", encoding="utf-8")] + [json.loads(l) for l in open(base / "table/test.jsonl", encoding="utf-8")]
    for i, r in enumerate(rng.sample(rows, min(n_table, len(rows)))):
        out.append(dict(id=f"bipia-table{i:04d}", kind="table", source="BIPIA-table", split_mode="line", text=normalize_text(r["context"])))
    return out

_MAP = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u2010": "-", "\u2011": "-",
        "\u2012": "-", "\u2212": "-", "\u2026": "...", "\u00a0": " ", "\u202f": " ", "\u2009": " ", "\u200a": " ", "\u2002": " ",
        "\u2003": " ", "\u200b": "", "\u00d7": "x", "\u2022": "-"}
def normalize_text(t):
    """Make carrier text typographically uniform so the source (LLM / Wikipedia / BIPIA) cannot be told apart by
    quote style, dash type or special spaces. Injection strings are NOT normalised (obfuscation is part of the attack)."""
    import re, unicodedata
    for k, v in _MAP.items(): t = t.replace(k, v)
    t = unicodedata.normalize("NFKC", t)
    return re.sub(r"[ \t]{2,}", " ", t)

def load_real():
    out = []
    for f in sorted(glob.glob(str(HERE / "carriers/real/*.jsonl"))):
        out += [dict(json.loads(l), text=normalize_text(json.loads(l)["text"])) for l in open(f, encoding="utf-8")]
    return out
