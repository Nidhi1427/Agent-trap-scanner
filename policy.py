"""Configurable document policy, kept separate from detector scoring."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "document_policy.json"


def load_policy(path=DEFAULT_CONFIG):
    config = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    rules = config["thresholds"]
    if not (0 <= rules["allow_below"] <= rules["hold_at_or_above"] <= rules["quarantine_at_or_above"] <= 1):
        raise ValueError("policy thresholds must satisfy 0 <= allow_below <= hold <= quarantine <= 1")
    return config


def decide(score, config):
    """Return a policy decision without changing or relabeling the raw score."""
    t = config["thresholds"]
    if score >= t["quarantine_at_or_above"]:
        decision = "quarantine"
    elif score >= t["hold_at_or_above"]:
        decision = "hold_for_review"
    else:
        decision = "allow"
    return {"decision": decision, "score": round(float(score), 4), "policy": config["name"]}


def apply_document(text, score, config=None, html=False, sanitizer=None):
    """Apply policy after screening; never touches source files or executes requests."""
    config = config or load_policy()
    result = decide(score, config)
    if result["decision"] == "allow":
        return {**result, "delivered_text": text, "review_flag": False, "sanitization": None}
    if result["decision"] == "quarantine":
        return {**result, "delivered_text": "", "review_flag": False,
                "sanitization": {"recorded_only": True, "artifact": "demo decision record"}}
    sanitized = sanitizer(text, html=html) if sanitizer else {"clean_text": text, "removed_spans": []}
    return {**result, "delivered_text": sanitized["clean_text"], "review_flag": True, "sanitization": sanitized}
