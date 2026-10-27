"""Can a model guess the label from superficial features (length, markup, position-free stats) alone?
Should be near 50% accuracy / 0.5 AUC. Much higher => the dataset leaks the label."""
import json, re, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
rows = [json.loads(l) for l in open("data/corpus.jsonl", encoding="utf-8")]
def feats(r):
    t, raw = r["text"], r["raw"]; w = t.split()
    return [len(t), len(w), t.count("\n"), np.mean([len(x) for x in w]) if w else 0, len(re.findall(r"<[a-z]", raw)),
            raw.count("<!--"), raw.count("display:none"), sum(c.isupper() for c in t) / max(len(t), 1), sum(c.isdigit() for c in t) / max(len(t), 1),
            sum(ord(c) > 127 for c in t), r["kind"] == "email", r["kind"] == "table", r["kind"] == "web"]
X = lambda sp: np.array([feats(r) for r in rows if r["split"] == sp], float); Y = lambda sp: np.array([r["label"] for r in rows if r["split"] == sp])
mu, sd = X("train").mean(0), X("train").std(0) + 1e-9
m = LogisticRegression(max_iter=2000).fit((X("train") - mu) / sd, Y("train"))
p = m.predict_proba((X("test") - mu) / sd)[:, 1]
print(f"shortcut model on test: accuracy {accuracy_score(Y('test'), p > .5):.3f}  AUC {roc_auc_score(Y('test'), p):.3f}   (want ~0.5)")
