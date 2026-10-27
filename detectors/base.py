"""Shared detector protocol and score validation."""
from typing import Protocol

class Detector(Protocol):
    name: str
    def score(self, texts: list[str]) -> list[float]: ...
    def details(self, text: str) -> dict: ...

def checked(detector, texts):
    values = list(detector.score(texts))
    if len(values) != len(texts) or any(not 0 <= float(x) <= 1 for x in values):
        raise ValueError(f"{detector.name} must return one [0,1] score per text")
    return [float(x) for x in values]
