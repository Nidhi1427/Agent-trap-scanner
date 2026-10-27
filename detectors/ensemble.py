"""Validation-only logistic stack over the three detector scores."""
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PATH=ROOT/'models'/'ensemble.json'
def sigmoid(x): return 1/(1+math.exp(-max(-30,min(30,x))))
class Ensemble:
    name='ensemble'
    def __init__(self,weights=None,bias=0.0): self.weights=weights or [0.0]*3; self.bias=bias
    def fit(self,X,y):
        w=[0.0]*len(X[0]); b=0.0
        for epoch in range(1200):
            rate=.08/(1+epoch/800)
            for x,label in zip(X,y):
                e=sigmoid(b+sum(a*v for a,v in zip(w,x)))-label
                b-=rate*e
                w=[a-rate*(e*v+.002*a) for a,v in zip(w,x)]
        self.weights=w; self.bias=b; return self
    def score(self,texts): raise RuntimeError('Ensemble needs score_features; use evaluate_all')
    def predict_features(self,X): return [sigmoid(self.bias+sum(a*v for a,v in zip(self.weights,x))) for x in X]
    def save(self,threshold,features):
        PATH.parent.mkdir(exist_ok=True); PATH.write_text(json.dumps({'model':'validation-logistic-stack','features':features,'weights':self.weights,'bias':self.bias,'threshold':threshold,'fit_split':'val'},indent=2)+'\n',encoding='utf-8')
