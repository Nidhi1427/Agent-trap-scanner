"""One-shot frozen test evaluation for detectors, combinations, and ensemble."""
import collections, hashlib, json, pathlib, subprocess
from datetime import datetime, timezone
from evaluate import load, metrics, pick_threshold, bootstrap_intervals, keyword_detector
from detectors.classifier import Classifier
from detectors.heuristics import Heuristics
from detectors.perplexity import Perplexity
from detectors.ensemble import Ensemble
ROOT=pathlib.Path(__file__).resolve().parent
def auth(row):
    s=row.get('carrier_source','')
    if s in ('wikipedia-human','BIPIA-email','BIPIA-table'): return 'human'
    return 'llm:'+s if s in ('gemini','groq-qwen','groq-gptoss') else 'unknown:'+str(s)
def safe_git():
    try: return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return 'unavailable'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def evaluate_all():
    train,val,test=load('train'),load('val'),load('test')
    # The held-out test data is read and scored once per final detector configuration here.
    detectors=[Classifier(),Heuristics(),Perplexity([r['text'] for r in train if r['label']==0])]
    names=[d.name for d in detectors]
    val_features={n:d.score([r['text'] for r in val]) for n,d in zip(names,detectors)}
    test_features={n:d.score([r['text'] for r in test]) for n,d in zip(names,detectors)}
    val_features['keyword']=keyword_detector([r['text'] for r in val]); test_features['keyword']=keyword_detector([r['text'] for r in test])
    labels_v=[r['label'] for r in val]; labels=[r['label'] for r in test]
    groups={
      'classifier':(['classifier'],lambda xs:xs[0]), 'heuristics':(['heuristics'],lambda xs:xs[0]), 'perplexity':(['perplexity'],lambda xs:xs[0]), 'keyword':(['keyword'],lambda xs:xs[0]),
      'classifier+heuristics':(['classifier','heuristics'],max), 'classifier+perplexity':(['classifier','perplexity'],max), 'heuristics+perplexity':(['heuristics','perplexity'],max), 'all_three':(['classifier','heuristics','perplexity'],max)
    }
    resultset={}; test_scores={}
    for name,(cols,combine) in groups.items():
        vs=[combine([val_features[c][i] for c in cols]) for i in range(len(val))]
        ts=[combine([test_features[c][i] for c in cols]) for i in range(len(test))]
        resultset[name]=_record(name,vs,ts,labels_v,labels,val,test); test_scores[name]=ts
    Xv=[[val_features[n][i] for n in names] for i in range(len(val))]; Xt=[[test_features[n][i] for n in names] for i in range(len(test))]
    ens=Ensemble().fit(Xv,labels_v); ev=ens.predict_features(Xv); et=ens.predict_features(Xt)
    ens_threshold=pick_threshold(ev,labels_v,.10); ens.save(ens_threshold,names)
    resultset['ensemble']=_record('ensemble',ev,et,labels_v,labels,val,test)
    # Threshold for 5% validation FPR; report test TPR at that frozen operating point.
    for name,rec in resultset.items():
        cols,combine=groups.get(name,(names,lambda xs:xs[0]))
        vs=ev if name=='ensemble' else [combine([val_features[c][i] for c in cols]) for i in range(len(val))]
        ts=et if name=='ensemble' else test_scores[name]
        t5=pick_threshold(vs,labels_v,.05)
        rec['tpr_at_5pct_fpr']={'validation_threshold':t5,'test_recall':sum(s>=t5 and y==1 for s,y in zip(ts,labels))/max(sum(labels),1)}
        rec['tpr_at_5pct_fpr']['bootstrap_95_carrier_ci']=list(bootstrap_intervals(ts,labels,[r['carrier_id'] for r in test],t5,samples=400,seed=1).get('recall',(float('nan'),float('nan'))))
    # Thresholds are selected solely on validation scores and persisted for reproducibility.
    tuned={n:{'threshold':pick_threshold(val_features[n],labels_v,.10),'tuned_on':'val','target_fpr_strictly_below':.10} for n in ('classifier','heuristics','perplexity','keyword')}
    tuned['ensemble']={'threshold':ens_threshold,'weights':ens.weights,'bias':ens.bias,'features':names,'tuned_on':'val','target_fpr_strictly_below':.10}
    (ROOT/'config/detector_thresholds.json').write_text(json.dumps(tuned,indent=2)+'\n',encoding='utf-8')
    policy_path=ROOT/'config/document_policy.json'; policy=json.loads(policy_path.read_text(encoding='utf-8'))
    policy['thresholds']['allow_below']=ens_threshold; policy['thresholds']['hold_at_or_above']=ens_threshold
    policy['thresholds']['quarantine_at_or_above']=max(.75,ens_threshold)
    policy['description']='Allow below the ensemble validation-selected threshold; hold above it; record quarantine at the configured higher score. All decisions are screening signals.'
    policy_path.write_text(json.dumps(policy,indent=2)+'\n',encoding='utf-8')
    corpus=ROOT/'data/corpus.jsonl'; manifest=json.loads((ROOT/'data/manifest.json').read_text(encoding='utf-8'))
    allrows=train+val+test
    sources={s:len({r['carrier_id'] for r in allrows if auth(r)==s}) for s in sorted({auth(r) for r in allrows})}
    source_slices={}
    for source in sorted(set(auth(r) for r in test)):
        ix=[i for i,r in enumerate(test) if auth(r)==source]; clean=[i for i in ix if labels[i]==0]; pos=[i for i in ix if labels[i]==1]
        source_slices[source]={'carriers':len({test[i]['carrier_id'] for i in ix}), 'rows':len(ix),'fpr':sum(et[i]>=ens_threshold for i in clean)/max(len(clean),1),'recall':sum(et[i]>=ens_threshold for i in pos)/max(len(pos),1)}
    # Independent removal quality, computed from the same single scored test pass.
    from sanitize import sanitize
    removed_injected=total_injected=0; clean_removed_chars=clean_total_chars=0; residual_sum=0.0
    for row in test:
        result=sanitize(row['text'],html=(row.get('kind')=='web' and '<' in row['text']))
        residual_sum+=result['residual_score']
        removed=' '.join(x['text'] for x in result['removed_spans'])
        if row['label']:
            total_injected+=1; attack=row.get('injection') or ''
            if attack and attack not in result['clean_text']: removed_injected+=1
        else:
            clean_total_chars+=len(row['text']); clean_removed_chars+=min(len(row['text']),sum(len(x['text']) for x in result['removed_spans']))
    removal={'injected_string_removal_fraction':removed_injected/max(total_injected,1),'injected_rows':total_injected,'injected_strings_removed':removed_injected,'clean_character_false_removal_fraction':clean_removed_chars/max(clean_total_chars,1),'clean_chars_removed_estimate':clean_removed_chars,'clean_chars_total':clean_total_chars,'residual_score_mean':residual_sum/len(test),'method':'exact injection string absence; clean char removal estimated from returned removed spans; diagnostic only'}
    from evasion_eval import run as run_evasion
    evasion=run_evasion()
    config_files=[ROOT/'config/detector_thresholds.json',ROOT/'config/heuristics.json',ROOT/'config/perplexity.json',ROOT/'config/document_policy.json']
    payload={'detector':'frozen-seed0 research evaluation','created_utc':datetime.now(timezone.utc).isoformat(),'git_commit':safe_git(),'seed':manifest['seed'],'corpus_sha256':manifest['corpus_sha256'],'model_sha256':sha(ROOT/'models/agent_trap_model.json'),'ensemble_sha256':sha(ROOT/'models/ensemble.json'),'config_sha256':{x.relative_to(ROOT).as_posix():sha(x) for x in config_files},'test_access':'single evaluation pass; thresholds and ensemble fit on val only','splits':manifest['split_counts'],'authorship_counts':sources,'source_test_slices':source_slices,'llm_carrier_counts':{k:v for k,v in sources.items() if k.startswith('llm:')},'gemini_limitation':'Only 23 Gemini carriers total; source estimates are limited.','results':resultset,'removal_quality':removal,'evasion':evasion,'tuned_parameters':tuned,'perplexity_backend':detectors[2].backend,'optional_transformer':'distilgpt2 loaded only from local cache if present; otherwise clean-train n-gram fallback; no network attempted','external_classifier_baseline':'not run (optional dependencies/weights not present; no network downloads)','baselines':{'keyword':resultset['keyword'],'published_rows':'BIPIA (Yi et al., arXiv:2312.14197) reports LLM attack/defense outcomes on a different task and is not a directly comparable text-classifier row; no accuracy/FPR number copied. External classifier not run.'},'targets':{'accuracy_minimum':.85,'fpr_strict_maximum':.10,'ensemble_accuracy_pass':resultset['ensemble']['test']['accuracy']>=.85,'ensemble_fpr_pass':resultset['ensemble']['test']['fpr']<.10},'limitations':['English-only, text-only, paired 50/50 benchmark.','Gemini has 23 carriers total.','Screening signal, not proof of compromise.']}
    (ROOT/'reports').mkdir(exist_ok=True)
    for n,r in resultset.items(): (ROOT/'reports'/f'{n}.json').write_text(json.dumps({'name':n,**r,'git_commit':safe_git(),'seed':manifest['seed'],'corpus_sha256':manifest['corpus_sha256'],'model_sha256':payload['model_sha256'],'config_sha256':payload['config_sha256']},indent=2)+'\n',encoding='utf-8')
    (ROOT/'reports'/'ablation.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print('Detector / Accuracy / FPR / Recall / Precision / AUROC / TPR@5%FPR')
    for n,r in resultset.items():
        m=r['test']; print(f"{n:24} {m['accuracy']:.3f} {m['fpr']:.3f} {m['recall']:.3f} {m['precision']:.3f} {m['auroc']:.3f} {r['tpr_at_5pct_fpr']['test_recall']:.3f}")
    return payload
def _record(name,vs,ts,yv,y,vr,tr):
    threshold=pick_threshold(vs,yv,.10); m=metrics(ts,y,threshold); ci=bootstrap_intervals(ts,y,[r['carrier_id'] for r in tr],threshold,samples=400,seed=0)
    pred=[s>=threshold for s in ts]; slices={}
    for key in ('style','hiding','position','kind','carrier_source'):
        groups=collections.defaultdict(list)
        for i,row in enumerate(tr): groups[str(row.get(key,'unknown'))].append(i)
        slices[key]={}
        for k,ix in groups.items():
            pos=[i for i in ix if y[i]==1]; neg=[i for i in ix if y[i]==0]
            slices[key][k]={}
            if pos: slices[key][k]['recall']=sum(pred[i] for i in pos)/len(pos)
            if neg: slices[key][k]['fpr']=sum(pred[i] for i in neg)/len(neg)
    return {'threshold':threshold,'threshold_selected_on':'val','test':m,'bootstrap_95_carrier_ci':{k:list(v) for k,v in ci.items()},'slices':slices}
if __name__=='__main__': evaluate_all()
