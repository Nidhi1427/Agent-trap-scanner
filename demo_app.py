"""Offline interactive demo server. Run py -3.14 demo_app.py."""
import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from detectors.classifier import Classifier
from detectors.heuristics import Heuristics
from detectors.perplexity import Perplexity
from detectors.ensemble import Ensemble, sigmoid
from sanitize import sanitize
from policy import load_policy, apply_document
from tool_auth import MockExecutor, authorize_and_execute
from extract import extract_text

ROOT=Path(__file__).resolve().parent
SAMPLES=json.loads((ROOT/'demo/examples.json').read_text(encoding='utf-8'))
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/api/benchmark':
            p=ROOT/'reports/ablation.json'
            body=p.read_bytes() if p.exists() else b'{}'; typ='application/json'
        elif self.path=='/api/samples': body=json.dumps(SAMPLES).encode(); typ='application/json'
        elif self.path=='/api/components':
            p=ROOT/'reports/demo_results.json'; body=p.read_bytes() if p.exists() else b'{}'; typ='application/json'
        else:
            p=ROOT/'index.html' if self.path in ('/','/index.html') else ROOT/self.path.lstrip('/')
            if not p.is_file() or ROOT not in p.resolve().parents: self.send_error(404); return
            body=p.read_bytes(); typ='text/html; charset=utf-8' if p.suffix=='.html' else 'application/octet-stream'
        self.send_response(200); self.send_header('Content-Type',typ); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        try:
            data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            if self.path=='/api/scan': out=scan_document(data)
            elif self.path=='/api/tool':
                executor=MockExecutor(); out=authorize_and_execute(data,executor); out['mock_executor_calls']=executor.calls
            else: self.send_error(404); return
            body=json.dumps(out,ensure_ascii=False).encode('utf-8'); self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        except Exception as e:
            body=json.dumps({'error':str(e)}).encode(); self.send_response(400); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
def scan_document(data):
    text=str(data.get('text','')); html=bool(data.get('html'))
    c=Classifier(); h=Heuristics(); p=Perplexity()
    candidate=extract_text(text,'web') if html else text
    features=[c.score([candidate])[0],h.score([text])[0],p.score([candidate])[0]]
    m=json.loads((ROOT/'models/ensemble.json').read_text(encoding='utf-8'))
    score=sigmoid(m['bias']+sum(a*b for a,b in zip(m['weights'],features))); threshold=m['threshold']
    action=apply_document(text,score,load_policy(),html=html,sanitizer=lambda t,html=False:sanitize(t,html))
    decision=action['decision']
    if decision=='quarantine':
        cleaning=sanitize(text,html)
    else:
        cleaning=action.get('sanitization') or {'clean_text':text,'removed_spans':[],'original_score':round(features[0],4),'residual_score':round(features[0],4)}
    return {'scores':dict(zip(['classifier','heuristics','perplexity'],[round(x,4) for x in features])),'perplexity_backend':p.backend,'ensemble_score':round(score,4),'ensemble_threshold':threshold,'rules_fired':h.details(text),'policy':action,'sanitization':cleaning,'agent_view':action['delivered_text'],'review_flag':action['review_flag'],'final_outcome':'withheld_quarantine' if decision=='quarantine' else ('sanitized_for_review' if decision=='hold_for_review' else 'passed_allow'),'notice':'Screening signal, not proof of compromise.'}
def main():
    server=ThreadingHTTPServer(('127.0.0.1',8000),Handler)
    print('Offline demo ready at http://localhost:8000 (Ctrl+C to stop)')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=='__main__': main()
