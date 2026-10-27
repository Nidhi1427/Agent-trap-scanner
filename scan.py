"""Scan plain text or HTML for likely prompt-injection strings."""
import argparse
import json
import pathlib
import sys

from extract import extract_text
from train import MODEL_PATH, score_text, vectorize


def load_model(path):
    artifact = json.loads(path.read_text(encoding="utf-8"))
    required = ("vocabulary", "idf", "weights", "bias", "threshold")
    if any(key not in artifact for key in required):
        raise ValueError(f"{path} is not a supported scanner model")
    return artifact


def prepare_text(raw, is_html):
    return extract_text(raw, "web") if is_html else raw


def explain(text, model, limit=5):
    features = vectorize(text, model["vocabulary"], model["idf"])
    contributions = sorted(
        ((model["weights"][index] * features[index], feature)
         for feature, index in model["vocabulary"].items()
         if index in features),
        key=lambda item: abs(item[0]), reverse=True
    )[:limit]
    return [{"feature": feature, "direction": "injection" if weight > 0 else "benign", "contribution": round(weight, 4)}
            for weight, feature in contributions]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Flag possible prompt-injection text. A match is a screening signal, not proof of compromise.")
    parser.add_argument("input", nargs="?", help="text/HTML file; omit to read plain text from stdin")
    parser.add_argument("--html", action="store_true", help="parse the input as HTML and include visible/hidden text and selected attributes")
    parser.add_argument("--model", type=pathlib.Path, default=MODEL_PATH, help="trained model JSON path")
    parser.add_argument("--threshold", type=float, help="override the validation-selected threshold")
    args = parser.parse_args(argv)
    if not args.model.is_file():
        parser.error(f"model not found at {args.model}; run `py -3.14 train.py` first")
    try:
        model = load_model(args.model)
        raw = pathlib.Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        is_html = args.html or (args.input and pathlib.Path(args.input).suffix.lower() in (".html", ".htm"))
        text = prepare_text(raw, bool(is_html))
        threshold = model["threshold"] if args.threshold is None else args.threshold
        score = score_text(text, model["vocabulary"], model["idf"], model["weights"], model["bias"])
        result = {
            "label": "possible_injection" if score >= threshold else "no_match",
            "score": round(score, 4),
            "threshold": round(threshold, 4),
            "word_count": len(text.split()),
            "flags": ["html_candidate_text_extracted"] if is_html else [],
            "top_features": explain(text, model),
            "notice": "A detector score is a screening signal, not proof of authorship, intent, or successful compromise.",
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
