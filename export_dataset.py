"""Package the active regenerated corpus into train/validation/test JSONL files."""
import json, pathlib, collections
rows = [json.loads(l) for l in open("data/corpus.jsonl", encoding="utf-8")]
out = pathlib.Path("export"); out.mkdir(exist_ok=True)
twin_ids = lambda style: {r["carrier_id"] for r in rows if r["label"] == 1 and r["style"] == style}
ood, evas = twin_ids("authority_notice"), twin_ids("bipia_obfuscated")
def part(r):
    if r["split"] != "test": return r["split"]
    if r["carrier_id"] in evas: return "evasion_test"
    if r["carrier_id"] in ood: return "test_ood"
    return "test"
groups = collections.defaultdict(list)
for r in rows: groups[part(r)].append(r)
slim = ("id", "text", "label")
for name, rs in groups.items():
    with open(out / f"{name}.jsonl", "w", encoding="utf-8") as f, open(out / f"{name}_full.jsonl", "w", encoding="utf-8") as g:
        for r in rs:
            f.write(json.dumps({k: r[k] for k in slim}, ensure_ascii=False) + "\n"); g.write(json.dumps(r, ensure_ascii=False) + "\n")
lines = ["# Agent Trap Scanner dataset datasheet", "",
         "Task: binary text-level screening for an inserted prompt-injection string (1) versus its clean carrier (0). A positive label does not mean an agent followed the string or that harm occurred.", "",
         "| file | clean | injected | rows |", "|---|---:|---:|---:|"] + [f"| {n}.jsonl | {sum(r['label']==0 for r in rs)} | {sum(r['label']==1 for r in rs)} | {len(rs)} |" for n, rs in sorted(groups.items())]
srcs = collections.Counter(r["carrier_source"] for r in rows if r["label"] == 0); atk = collections.Counter(r["attack_source"] for r in rows if r["label"] == 1)
kind_counts = collections.Counter(r["kind"] for r in rows if r["label"] == 0)
lines += ["", "Carrier sources: " + ", ".join(f"{k}={v}" for k, v in sorted(srcs.items())),
          "Carrier kinds: " + ", ".join(f"{k}={v}" for k, v in sorted(kind_counts.items())),
          "Attack sources: " + ", ".join(f"{k}={v}" for k, v in sorted(atk.items())),
          "", "Use train.jsonl for fitting and validation.jsonl for tuning. Keep test.jsonl, test_ood.jsonl, and evasion_test.jsonl for final evaluation. Carrier pairs stay in a single split; exact injected strings are not reused across splits.",
          "test_ood.jsonl holds out the team-authored authority_notice framing; its underlying attack goals are reused from InjecAgent. evasion_test.jsonl contains BIPIA obfuscation categories. These are limited held-out settings, not proof of generalization to every unseen attack.",
          "The corpus is English-only, text-only, and balanced by construction. Precision/F1 do not estimate deployment performance without a realistic prevalence. Source datasets have separate licenses; review each upstream license before redistribution."]
open(out / "DATASHEET.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines[4:4 + len(groups) + 2]))
