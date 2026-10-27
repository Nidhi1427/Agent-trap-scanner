"""python build_corpus.py [--n 1500] [--seed 0] -> data/corpus.jsonl
Each carrier yields a PAIR: one clean doc and one injected doc (injection style/position/hiding sampled).
Splits are by carrier AND by exact injection string (no string shared across splits)."""
import json, random, argparse, html as H, collections, hashlib, pathlib
from attacks import build_attack_pool
from carriers import make_toy_carriers, load_real, load_bipia
from extract import extract_text

POSITIONS = ["head", "middle", "tail"]
HIDING = ["none", "css_display_none", "white_on_white", "html_comment", "zero_font", "aria_label"]
TRAIN_STYLES = ["override_ops", "agent_tool", "latent_task", "bipia_text", "bipia_code"]
OOD_STYLES = ["authority_notice", "bipia_obfuscated"]   # test split only

def wrap_hidden(txt, method):
    e = H.escape(txt)
    return {"none": f"<p>{e}</p>",
            "css_display_none": f'<div style="display:none">{e}</div>',
            "white_on_white": f'<p style="color:#ffffff;background:#ffffff">{e}</p>',
            "html_comment": f"<!-- {txt.replace('--','- -')} -->",
            "zero_font": f'<span style="font-size:0px">{e}</span>',
            "aria_label": f'<img src="x.png" alt="{H.escape(txt, quote=True)}">'}[method]

def benign_hidden(rng):
    return rng.choice(['<nav style="display:none">Home | About | Contact</nav>', "<!-- end of header -->",
        '<button aria-label="Close menu">x</button>', '<span style="font-size:0px">.</span>',
        '<img src="logo.png" alt="Company logo">'])

def paragraphs(c):
    import re
    m = c.get("split_mode")
    if m == "sentence":
        return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", c["text"]) if x.strip()]
    if m == "line":
        return [x for x in c["text"].split("\n") if x.strip()]
    if "sentences" in c:
        s = c["sentences"]; return [" ".join(s[i:i+3]) for i in range(0, len(s), 3)]
    return [p.strip() for p in c["text"].split("\n\n") if p.strip()]

def insert_at(blocks, block, pos):
    n = len(blocks)
    i = {"head": 0, "middle": n // 2, "tail": n}[pos]
    return blocks[:i] + [block] + blocks[i:]

def render(c, blocks, kind):
    if kind == "web":
        return f"<html><body><h1>{H.escape(c.get('topic','Page'))}</h1>" + "".join(blocks) + "</body></html>"
    return ("\n" if kind in ("table", "email") else "\n\n").join(blocks)

def make_doc(c, attack, pos, hiding, benign=None, benign_pos="head"):
    kind = c["kind"]
    if kind == "web": blocks = [f"<p>{H.escape(p)}</p>" for p in paragraphs(c)]
    else: blocks = paragraphs(c)
    if benign and kind == "web": blocks = insert_at(blocks, benign, benign_pos)
    if attack:
        blk = wrap_hidden(attack["text"], hiding) if kind == "web" else attack["text"]
        blocks = insert_at(blocks, blk, pos)
    raw = render(c, blocks, kind)
    return raw, extract_text(raw, kind)

def main(n, seed, toy=False):
    rng = random.Random(seed)
    carriers = ([] if toy else load_real() + load_bipia()) or make_toy_carriers(n, seed)
    using_toy = carriers[0]["source"] == "toy"
    carriers.sort(key=lambda c: c["id"])
    rng.shuffle(carriers)
    seen, pool = set(), []
    for a in build_attack_pool(seed):  # dedupe so no exact string can land in two splits
        if a['text'] not in seen: seen.add(a['text']); pool.append(a)
    parts = {s: {"train": [], "val": [], "test": []} for s in TRAIN_STYLES + OOD_STYLES}
    for a in pool:
        r = rng.random()
        if a.get("fixed") == "test": sp = "test"                       # BIPIA's own held-out categories
        elif a.get("fixed") == "trainval": sp = "train" if r < .82 else "val"
        else: sp = "train" if r < .7 else "val" if r < .85 else "test"
        parts[a["style"]][sp].append(a)
    rows = []
    for i, c in enumerate(carriers):
        split = "train" if i < .7*len(carriers) else "val" if i < .85*len(carriers) else "test"
        style = rng.choice(TRAIN_STYLES + (OOD_STYLES if split == "test" else []))
        atk = rng.choice(parts[style][split]); pos = rng.choice(POSITIONS)
        hiding = rng.choice(HIDING) if c["kind"] == "web" else "none"
        benign = benign_hidden(rng) if rng.random() < .3 and c["kind"] == "web" else None
        benign_pos = rng.choice(POSITIONS)
        for label in (0, 1):
            raw, text = make_doc(c, atk if label else None, pos, hiding, benign, benign_pos)
            rows.append(dict(id=f'{c["id"]}-{label}', carrier_id=c["id"], split=split, label=label,
                kind=c["kind"], carrier_source=c["source"], hard_negative=bool(c.get("hard_negative")) or bool(benign),
                style=style if label else None, sub=atk["sub"] if label else None,
                attack_source=atk["source"] if label else None, position=pos if label else None,
                hiding=hiding if label else None, ood_style=bool(label and style in OOD_STYLES),
                injection=atk["text"] if label else None, raw=raw, text=text))
    data_dir = pathlib.Path("data")
    data_dir.mkdir(exist_ok=True)
    corpus_path = data_dir / "corpus.jsonl"
    with corpus_path.open("w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    inputs = sorted(pathlib.Path("carriers/real").glob("*.jsonl"))
    inputs += [
        pathlib.Path("raw/BIPIA/benchmark/email/train.jsonl"), pathlib.Path("raw/BIPIA/benchmark/email/test.jsonl"),
        pathlib.Path("raw/BIPIA/benchmark/table/train.jsonl"), pathlib.Path("raw/BIPIA/benchmark/table/test.jsonl"),
        pathlib.Path("raw/BIPIA/benchmark/text_attack_train.json"), pathlib.Path("raw/BIPIA/benchmark/text_attack_test.json"),
        pathlib.Path("raw/BIPIA/benchmark/code_attack_train.json"), pathlib.Path("raw/BIPIA/benchmark/code_attack_test.json"),
        pathlib.Path("raw/InjecAgent/data/attacker_cases_dh.jsonl"), pathlib.Path("raw/InjecAgent/data/attacker_cases_ds.jsonl"),
        pathlib.Path("raw/garak/garak/data/payloads/normal_instructions.json"),
        pathlib.Path("build_corpus.py"), pathlib.Path("attacks.py"), pathlib.Path("carriers.py"), pathlib.Path("extract.py"),
    ]
    input_hashes = {}
    for path in inputs:
        if path.exists():
            input_hashes[path.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "dataset": "agent-trap-scanner",
        "version": 1,
        "seed": seed,
        "toy_carriers": using_toy,
        "rows": len(rows),
        "carriers": len(carriers),
        "split_counts": {split: dict(collections.Counter(str(r["label"]) for r in rows if r["split"] == split))
                         for split in ("train", "val", "test")},
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "input_sha256": input_hashes,
    }
    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows ({'TOY carriers - pipeline test only' if using_toy else 'real carriers'})")
    print(collections.Counter((r["split"], r["label"]) for r in rows))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=800); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--toy", action="store_true", help="use toy carriers (pipeline test only)")
    a = ap.parse_args(); main(a.n, a.seed, a.toy)
