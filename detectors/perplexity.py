"""Offline window anomaly scorer with clean-train n-gram fallback and optional distilgpt2."""
import collections, json, math, pathlib, re
ROOT=pathlib.Path(__file__).resolve().parents[1]; CACHE=ROOT/'cache'/'ppl.jsonl'; CONFIG=ROOT/'config'/'perplexity.json'
TOK=re.compile(r"[\w']+",re.UNICODE)
def words(t): return [x.casefold() for x in TOK.findall(t)]
class Perplexity:
    name='perplexity'
    def __init__(self, train_texts=None, backend='auto'):
        self.cache={}
        if CACHE.exists():
            for line in CACHE.read_text(encoding='utf-8').splitlines():
                try:
                    r=json.loads(line); self.cache[r['sha']]=r['result']
                except (ValueError,KeyError): pass
        self.backend='ngram'; self.lm=None
        if backend in ('auto','distilgpt2'):
            try:
                import torch
                from transformers import AutoTokenizer, AutoModelForCausalLM
                self.tokenizer=AutoTokenizer.from_pretrained('distilgpt2',local_files_only=True)
                self.lm=AutoModelForCausalLM.from_pretrained('distilgpt2',local_files_only=True).eval()
                self.torch=torch; self.backend='distilgpt2-local'
            except Exception: self.lm=None
        self.uni=collections.Counter(); self.bi=collections.Counter(); self.ctx=collections.Counter()
        for t in train_texts or []:
            ws=['<s>']+words(t)+['</s>']; self.uni.update(ws); self.bi.update(zip(ws,ws[1:])); self.ctx.update(ws[:-1])
        self.vocab=max(len(self.uni),1); self.window=40
        if train_texts is None and not self.uni:
            from evaluate import load
            self.__init__([r['text'] for r in load('train') if r['label']==0],backend); return
    def _ngram(self, ws):
        return [-math.log((self.bi[(a,b)]+0.1)/(self.ctx[a]+0.1*self.vocab)) for a,b in zip(ws,ws[1:])]
    def details(self,text):
        import hashlib
        key=hashlib.sha256((self.backend+'\0'+text).encode('utf-8')).hexdigest()
        if key in self.cache: return self.cache[key]
        ws=words(text)
        if len(ws)<3: result={'score':0.0,'backend':self.backend,'windows':0,'max_z':0.0,'window':self.window}; self.cache[key]=result; return result
        losses=self._ngram(['<s>']+ws)
        if self.lm is not None:
            ids=self.tokenizer(text,return_tensors='pt').input_ids
            with self.torch.no_grad():
                out=self.lm(ids,labels=ids)
                logits=out.logits[:,:-1,:].reshape(-1,out.logits.shape[-1]); targets=ids[:,1:].reshape(-1)
                losses=self.torch.nn.functional.cross_entropy(logits,targets,reduction='none').cpu().tolist()
        # Surprisal anomaly relative to document's own median; logistic maps z to [0,1].
        per_token=losses
        med=sorted(per_token)[len(per_token)//2]; windows=[sum(per_token[i:i+self.window])/max(len(per_token[i:i+self.window]),1) for i in range(0,len(per_token),max(self.window//2,1))]
        scale=math.sqrt(sum((x-med)**2 for x in per_token)/max(len(per_token),1))+1e-6
        z=max(windows,default=med)-med
        z=max(0.0,z/scale)
        score=1/(1+math.exp(-min(20,z-1.5)))
        result={'score':score,'backend':self.backend,'windows':len(windows),'max_z':z,'window':self.window}
        self.cache[key]=result
        CACHE.parent.mkdir(parents=True,exist_ok=True)
        with CACHE.open('a',encoding='utf-8') as f: f.write(json.dumps({'sha':key,'result':result})+'\n')
        return result
    def score(self,texts): return [self.details(t)['score'] for t in texts]
