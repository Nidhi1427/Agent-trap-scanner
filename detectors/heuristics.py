"""Interpretable, validation-thresholded prompt injection indicators."""
import json, re, unicodedata
from pathlib import Path
from extract import extract_segments
ROOT=Path(__file__).resolve().parents[1]
CONF=json.loads((ROOT/'config/heuristics.json').read_text(encoding='utf-8'))
OVERRIDE=re.compile(r"\b(ignore|disregard|override|forget|bypass|replace)\b.{0,70}\b(previous|prior|system|developer|all|above|instructions?|rules?|prompt)\b|\b(reveal|print|expose)\b.{0,40}\b(system prompt|hidden prompt|secrets?)\b",re.I)
IMPERATIVE=re.compile(r"\b(ignore|reveal|send|exfiltrate|execute|delete|disable|bypass|override|print|forward|upload|transfer|provide|return)\b",re.I)
SENSITIVE=re.compile(r"\b(system prompt|developer message|tool calls?|api keys?|passwords?|credentials?|exfiltrat\w*|attacker|secret|confidential)\b|https?://|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",re.I)
ZERO={ord(c):None for c in '\u200b\u200c\u200d\ufeff\u2060'}
HOMO=str.maketrans({'а':'a','е':'e','о':'o','р':'p','с':'c','х':'x','у':'y','і':'i','ј':'j','к':'k','м':'m','т':'t','в':'b','н':'h'})
LEET=str.maketrans({'0':'o','1':'i','3':'e','4':'a','5':'s','7':'t','@':'a','$':'s'})
def normalize(text):
    s=unicodedata.normalize('NFKD',text.translate(ZERO).translate(HOMO))
    s=''.join(c for c in s if not unicodedata.combining(c))
    s=s.translate(LEET)
    s=re.sub(r'(?<!\w)(?:[A-Za-z]\s+){2,}[A-Za-z](?!\w)',lambda m:re.sub(r'\s+','',m.group()),s)
    return s
def inspect(text, html=False):
    n=normalize(text); fired=[]; w=CONF['weights']
    if OVERRIDE.search(n): fired.append(('override',w['override']))
    words=re.findall(r"[\w']+",n.lower()); count=sum(bool(IMPERATIVE.fullmatch(x)) for x in words)
    density=count/max(len(words),1)
    if count>=2 or (count and density>=0.035): fired.append(('imperative_density',min(w['imperative_density']*(1+density*5),0.3)))
    if SENSITIVE.search(n): fired.append(('sensitive_target',w['sensitive_target']))
    segments=extract_segments(text) if html or '<' in text else []
    channels=sorted({c for c,_ in segments if c in ('css_hidden','comment','attr')})
    if channels: fired.append(('hidden_channel',w['hidden_channel']))
    total=min(1.0,sum(x for _,x in fired))
    return {'score':total,'rules_fired':[x[0] for x in fired],'imperative_count':count,'imperative_density':round(density,5),'hidden_channels':channels,'normalized_match':bool(OVERRIDE.search(n))}
class Heuristics:
    name='heuristics'
    def score(self,texts): return [inspect(t)['score'] for t in texts]
    def details(self,text): return inspect(text)
