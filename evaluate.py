"""Evaluate a detector on data/corpus.jsonl.

A detector is a function: list[str] -> list[float] (higher = more likely injected).
The threshold is selected on validation data and applied unchanged to test data.
Confidence intervals resample carrier IDs so clean/injected pairs stay together.
"""
import json
import random
import re
import collections
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
CORPUS = ROOT / "data" / "corpus.jsonl"

def load(split):
    with CORPUS.open(encoding="utf-8") as f:
        return [r for r in map(json.loads, f) if r["split"] == split]


def pick_threshold(scores, labels, max_fpr=0.10):
    best = (None, -1.0)
    negatives = [i for i, label in enumerate(labels) if label == 0]
    for threshold in sorted(set(scores)):
        predicted = [score >= threshold for score in scores]
        fpr = sum(predicted[i] for i in negatives) / max(len(negatives), 1)
        accuracy = sum(predicted[i] == bool(labels[i]) for i in range(len(labels))) / max(len(labels), 1)
        if fpr < max_fpr and accuracy > best[1]:
            best = (threshold, accuracy)
    return best[0] if best[0] is not None else max(scores) + 1


def auc(scores, labels):
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return float("nan")
    ordered = sorted(zip(scores, labels), key=lambda item: item[0])
    positive_rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2
        positive_rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        index = end
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def average_precision(scores, labels):
    positives = sum(labels)
    if not positives:
        return float("nan")
    ordered = sorted(zip(scores, labels), key=lambda item: item[0], reverse=True)
    true_positives = false_positives = 0
    ap = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        group = ordered[index:end]
        group_positives = sum(label for _, label in group)
        true_positives += group_positives
        false_positives += len(group) - group_positives
        ap += (group_positives / positives) * (true_positives / (true_positives + false_positives))
        index = end
    return ap


def metrics(scores, labels, threshold):
    predicted = [score >= threshold for score in scores]
    tp = sum(p and y == 1 for p, y in zip(predicted, labels))
    fp = sum(p and y == 0 for p, y in zip(predicted, labels))
    tn = sum(not p and y == 0 for p, y in zip(predicted, labels))
    fn = sum(not p and y == 1 for p, y in zip(predicted, labels))
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "n": len(labels),
        "accuracy": (tp + tn) / max(len(labels), 1),
        "fpr": fp / max(fp + tn, 1),
        "recall": recall,
        "precision": precision,
        "f1": 2 * precision * recall / max(precision + recall, 1e-12),
        "auroc": auc(scores, labels),
        "average_precision": average_precision(scores, labels),
    }


def bootstrap_intervals(scores, labels, carrier_ids, threshold, samples=1000, seed=0):
    """Percentile 95% CIs from a carrier-cluster bootstrap, preserving paired rows."""
    grouped = collections.defaultdict(list)
    for i, carrier_id in enumerate(carrier_ids):
        grouped[carrier_id].append(i)
    groups = list(grouped.values())
    if len(groups) < 2:
        return {}
    rng = random.Random(seed)
    names = ("accuracy", "fpr", "recall", "precision", "f1", "auroc", "average_precision")
    values = {name: [] for name in names}
    for _ in range(samples):
        sampled_rows = [i for group in rng.choices(groups, k=len(groups)) for i in group]
        result = metrics([scores[i] for i in sampled_rows], [labels[i] for i in sampled_rows], threshold)
        for name in names:
            if result[name] == result[name]:  # exclude NaN for one-class resamples
                values[name].append(result[name])
    intervals = {}
    for name, samples_for_name in values.items():
        if samples_for_name:
            samples_for_name.sort()
            intervals[name] = (samples_for_name[int(0.025 * (len(samples_for_name) - 1))],
                               samples_for_name[int(0.975 * (len(samples_for_name) - 1))])
    return intervals


def format_metric(name, value, intervals):
    low, high = intervals.get(name, (float("nan"), float("nan")))
    return f"{value:.3f} [{low:.3f}, {high:.3f}]"


def evaluate(detector, name="detector", max_fpr=0.10):
    val, test = load("val"), load("test")
    sv = list(detector([r["text"] for r in val]))
    yv = [r["label"] for r in val]
    st = list(detector([r["text"] for r in test]))
    yt = [r["label"] for r in test]
    if len(sv) != len(val) or len(st) != len(test):
        raise ValueError("detector must return exactly one score per input text")
    threshold = pick_threshold(sv, yv, max_fpr)
    result = metrics(st, yt, threshold)
    intervals = bootstrap_intervals(st, yt, [r["carrier_id"] for r in test], threshold)
    print(f"\n=== {name} (validation threshold {threshold:.3f}, target FPR < {max_fpr:.0%}) ===")
    print(f"TEST n={result['n']} rows / {len(set(r['carrier_id'] for r in test))} carriers")
    print("Metric (95% carrier-bootstrap CI):")
    for metric in ("accuracy", "fpr", "recall", "precision", "f1", "auroc", "average_precision"):
        print(f"  {metric}: {format_metric(metric, result[metric], intervals)}")

    # Slice rates are point estimates; interpret small slices cautiously.
    for key in ("kind", "carrier_source", "hard_negative"):
        groups = collections.defaultdict(list)
        for i, row in enumerate(test):
            if key == "hard_negative" and row["label"] != 0:
                continue
            groups[row[key]].append(i)
        for group, indices in sorted(groups.items(), key=lambda item: str(item[0])):
            positive = [i for i in indices if yt[i] == 1]
            negative = [i for i in indices if yt[i] == 0]
            rates = []
            if negative:
                false_positives = sum(st[i] >= threshold for i in negative)
                rates.append(f"FPR={false_positives / len(negative):.3f} (n={len(negative)} clean)")
            if positive:
                true_positives = sum(st[i] >= threshold for i in positive)
                rates.append(f"recall={true_positives / len(positive):.3f} (n={len(positive)} injected)")
            print(f"  {key}={group}: " + "; ".join(rates))

    for key in ("style", "position", "hiding", "attack_source"):
        groups = collections.defaultdict(list)
        for i, row in enumerate(test):
            if row["label"] == 1:
                groups[row[key]].append(i)
        print(f"  recall by {key}: " + "  ".join(
            f"{group}={sum(st[i] >= threshold for i in indices) / len(indices):.2f}(n={len(indices)})"
            for group, indices in sorted(groups.items(), key=lambda item: str(item[0]))
        ))
    return result


# Small lexical baseline. It is a sanity baseline, not a production scanner.
KEYWORDS = [r"ignore (all )?(previous|prior|above) instructions", r"disregard", r"strictly adhere", r"do not (mention|summarize)",
            r"system (message|prompt)", r"you must", r"as an ai", r"new instructions?", r"important!{2,}"]


def keyword_detector(texts):
    return [sum(bool(re.search(pattern, text, re.I)) for pattern in KEYWORDS) for text in texts]


if __name__ == "__main__":
    evaluate(keyword_detector, "keyword baseline")
