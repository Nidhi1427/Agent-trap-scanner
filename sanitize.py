"""Non-destructive, sentence and hidden-channel sanitizer for demo review."""
import re
from extract import extract_segments
from detectors.heuristics import inspect
from detectors.classifier import Classifier
from detectors.heuristics import CONF
_CLASSIFIER=None
def sanitize(text,html=False,threshold=None):
    global _CLASSIFIER
    if _CLASSIFIER is None: _CLASSIFIER=Classifier()
    classifier=_CLASSIFIER; threshold=classifier.model['threshold'] if threshold is None else threshold
    removed=[]; clean=text
    # HTML hidden/comment/attribute candidate channels are independently screened then removed if flagged.
    if html:
        segs=extract_segments(text)
        for channel,part in segs:
            if channel not in ('css_hidden','comment','attr'): continue
            hs=inspect(part)['score']; cs=classifier.score([part])[0]
            if max(hs,cs)>=threshold:
                removed.append({'text':part,'channel':channel,'reasons':['hidden_channel','detector_threshold'],'detector_scores':{'classifier':round(cs,4),'heuristics':round(hs,4)}})
                clean=clean.replace(part,'',1)
    # sentence level removal for visible/plain content; conservative at classifier threshold or explicit override rule
    for sentence in re.split(r'(?<=[.!?])\s+',clean):
        h=inspect(sentence); c=classifier.score([sentence])[0]
        if sentence.strip() and (h['normalized_match'] or c>=threshold):
            removed.append({'text':sentence,'channel':'visible','reasons':h['rules_fired'] or ['classifier_threshold'],'detector_scores':{'classifier':round(c,4),'heuristics':round(h['score'],4)}})
            clean=clean.replace(sentence,'',1)
    original=classifier.score([text])[0]; residual=classifier.score([clean])[0]
    return {'clean_text':clean,'removed_spans':removed,'original_score':round(original,4),'residual_score':round(residual,4)}
