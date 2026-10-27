"""Adapter for the frozen TF-IDF classifier artifact."""
import json
from pathlib import Path
from train import MODEL_PATH, score_text

class Classifier:
    name = "classifier"
    def __init__(self, path=MODEL_PATH): self.model=json.loads(Path(path).read_text(encoding="utf-8"))
    def score(self, texts):
        m=self.model
        return [score_text(t,m["vocabulary"],m["idf"],m["weights"],m["bias"]) for t in texts]
    def details(self, text): return {"score":self.score([text])[0],"threshold":self.model["threshold"],"model":self.model.get("model")}
