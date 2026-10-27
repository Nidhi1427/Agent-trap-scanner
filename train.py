"""Train a dependency-free TF-IDF logistic baseline from data/corpus.jsonl."""
import collections
import json
import math
import pathlib
import random
import re

from evaluate import evaluate, pick_threshold

ROOT = pathlib.Path(__file__).resolve().parent
CORPUS = ROOT / "data" / "corpus.jsonl"
MODEL_PATH = ROOT / "models" / "agent_trap_model.json"
TOKEN_RE = re.compile(r"[\w]+(?:['’][\w]+)?", re.UNICODE)
MAX_FEATURES = 30000
EPOCHS = 14
LEARNING_RATE = 0.18
L2 = 0.0001


def tokens(text):
    words = TOKEN_RE.findall(text.casefold())
    features = ["w:" + word for word in words]
    features.extend("b:" + words[i] + " " + words[i + 1] for i in range(len(words) - 1))
    return features


def load_rows(split):
    rows = []
    with CORPUS.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("split") == split:
                rows.append(row)
    return rows


def build_vocabulary(rows):
    document_frequency = collections.Counter()
    for row in rows:
        document_frequency.update(set(tokens(row["text"])))
    ranked = sorted(document_frequency, key=lambda feature: (-document_frequency[feature], feature))[:MAX_FEATURES]
    vocabulary = {feature: index for index, feature in enumerate(ranked)}
    count = len(rows)
    idf = [math.log((1 + count) / (1 + document_frequency[feature])) + 1 for feature in ranked]
    return vocabulary, idf


def vectorize(text, vocabulary, idf):
    counts = collections.Counter(tokens(text))
    values = {}
    for feature, count in counts.items():
        index = vocabulary.get(feature)
        if index is not None:
            values[index] = (1 + math.log(count)) * idf[index]
    norm = math.sqrt(sum(value * value for value in values.values()))
    if norm:
        for index in values:
            values[index] /= norm
    return values


def sigmoid(value):
    value = max(-35.0, min(35.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def train_model(train_rows, vocabulary, idf, seed=0):
    vectors = [vectorize(row["text"], vocabulary, idf) for row in train_rows]
    labels = [row["label"] for row in train_rows]
    weights = [0.0] * len(vocabulary)
    bias = 0.0
    rng = random.Random(seed)
    order = list(range(len(train_rows)))
    for epoch in range(EPOCHS):
        rng.shuffle(order)
        rate = LEARNING_RATE / (1 + 0.08 * epoch)
        for row_index in order:
            features = vectors[row_index]
            logit = bias + sum(weights[index] * value for index, value in features.items())
            error = sigmoid(logit) - labels[row_index]
            bias -= rate * error
            for index, value in features.items():
                weights[index] -= rate * (error * value + L2 * weights[index])
    return weights, bias


def score_text(text, vocabulary, idf, weights, bias):
    features = vectorize(text, vocabulary, idf)
    return sigmoid(bias + sum(weights[index] * value for index, value in features.items()))


def main():
    train_rows = load_rows("train")
    val_rows = load_rows("val")
    test_rows = load_rows("test")
    if not train_rows or not val_rows or not test_rows:
        raise SystemExit("data/corpus.jsonl must contain non-empty train, val, and test splits")
    vocabulary, idf = build_vocabulary(train_rows)
    weights, bias = train_model(train_rows, vocabulary, idf)
    validation_scores = [score_text(row["text"], vocabulary, idf, weights, bias) for row in val_rows]
    threshold = pick_threshold(validation_scores, [row["label"] for row in val_rows], max_fpr=0.10)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": "tfidf-logistic",
        "version": 1,
        "threshold": threshold,
        "target_validation_fpr": 0.10,
        "vocabulary": vocabulary,
        "idf": idf,
        "weights": weights,
        "bias": bias,
        "training_rows": len(train_rows),
        "feature_count": len(vocabulary),
        "seed": 0,
    }
    MODEL_PATH.write_text(json.dumps(artifact, separators=(",", ":")), encoding="utf-8")
    print(f"Saved {len(vocabulary):,} features from {len(train_rows):,} training rows to {MODEL_PATH}")

    def detector(texts):
        return [score_text(text, vocabulary, idf, weights, bias) for text in texts]

    evaluate(detector, "TF-IDF logistic baseline", max_fpr=0.10)


if __name__ == "__main__":
    main()
