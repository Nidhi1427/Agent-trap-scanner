"""Render current report-backed handoff documents after evaluation."""
import json,pathlib
R=pathlib.Path(__file__).resolve().parent/'reports'; d=json.loads((R/'ablation.json').read_text(encoding='utf-8'))
names=('classifier','heuristics','perplexity','keyword','classifier+heuristics','classifier+perplexity','heuristics+perplexity','all_three','ensemble')
table='| Method | Accuracy | FPR | Recall | Precision | AUROC | TPR@5% FPR |\n|---|---:|---:|---:|---:|---:|---:|\n'
for n in names:
 x=d['results'][n];m=x['test'];ci=x['bootstrap_95_carrier_ci'].get('accuracy',[0,0]);table+=f"| {n} | {m['accuracy']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] | {m['fpr']:.3f} | {m['recall']:.3f} | {m['precision']:.3f} | {m['auroc']:.3f} | {x['tpr_at_5pct_fpr']['test_recall']:.3f} |\n"
e=d['results']['ensemble']['test'];rm=d['removal_quality'];ev=d['evasion'];keyword=d['results']['keyword']['test']
report=f'''# Agent Trap Scanner — technical report

Generated from `reports/ablation.json` on {d['created_utc']}. Research demo; all detection thresholds and the ensemble fit use validation data only. The seed-0 corpus hash is `{d['corpus_sha256']}`; commit `{d['git_commit']}`; model SHA-256 `{d['model_sha256']}`. Detailed per-detector JSON, bootstrap intervals, and slices are in `reports/`.

## Method and trade-offs

The lexical classifier is a dependency-free TF-IDF unigram/bigram logistic model. The hand-set heuristic layer normalizes selected spaced letters, common leetspeak, zero-width marks, and Unicode compatibility forms; it flags override patterns, imperative density, sensitive targets, and HTML hidden/comment/attribute channels. These rules are inspectable but brittle and can false-positive. The perplexity signal compares 40-token windows using maximum local surprisal against a document median. Backend used: **{d['perplexity_backend']}**. The fallback is a word n-gram model trained from clean TRAIN documents only; local distilgpt2 weights are used only if already cached. Per-document scores are cached in `cache/ppl.jsonl`. This feature is an anomaly signal, not a semantic detector. A logistic stack is fitted on validation scores for the classifier, heuristics, and perplexity. Max-score pairs/all-three are reported as simple ablations. Sanitization removes flagged sentence or hidden-channel text into a returned preview; source documents are never edited. Policy is a separate allow/hold/quarantine layer, and tool authorization checks a named allowlist before the mock executor.

## Data, splits, and benchmark

Frozen active corpus: **3,400 rows / 1,700 paired carriers**, seed {d['seed']}; train/validation/test sizes are 2,380/510/510. It is paired and 50/50 by construction. Authorship carrier counts are `{json.dumps(d['authorship_counts'],sort_keys=True)}` (BIPIA email/table are grouped as human for this source attribution; they remain separate in carrier-source slice reports). LLM sources include Qwen, GPT-OSS, and Gemini; Gemini has only 23 carriers, so the source slice is not stable. The older `agent_trap_bipia/` dataset is excluded.

Thresholds were selected on validation to keep FPR strictly below 10%; test scores are reported once for the final configuration. Bootstrap intervals resample carrier IDs to preserve clean/injected pairs. **Ensemble test accuracy {e['accuracy']:.3f}; FPR {e['fpr']:.3f}; recall {e['recall']:.3f}; AUROC {e['auroc']:.3f}.** Accuracy target ≥0.85: {'PASS' if e['accuracy']>=.85 else 'FAIL'}. FPR target <0.10: {'PASS' if e['fpr']<.10 else 'FAIL'}.

## Ablation and baselines

{table}
The ensemble does **not** beat the best single detector on every measure: classifier accuracy is {d['results']['classifier']['test']['accuracy']:.3f} versus ensemble {e['accuracy']:.3f}; classifier AUROC is {d['results']['classifier']['test']['auroc']:.3f} versus ensemble {e['auroc']:.3f}. Keyword baseline on the same test set: accuracy {keyword['accuracy']:.3f}, FPR {keyword['fpr']:.3f}, recall {keyword['recall']:.3f}, AUROC {keyword['auroc']:.3f}. An external pretrained classifier was **not run**; no weights were downloaded. BIPIA reports model attack outcomes and defense effectiveness on different tasks and cannot be compared numerically to this text-classification accuracy/FPR; no paper score is copied. See [Yi et al., BIPIA, arXiv:2312.14197](https://arxiv.org/abs/2312.14197).

| Baseline | Same test set? | Result | Interpretation |
|---|---|---|---|
| Keyword rules | Yes | accuracy {keyword['accuracy']:.3f}; FPR {keyword['fpr']:.3f}; recall {keyword['recall']:.3f}; AUROC {keyword['auroc']:.3f} | Simple lexical reference |
| External pretrained injection classifier | No | Not run | Optional model package/weights were unavailable locally; no network download attempted |
| BIPIA paper (Yi et al.) | No | Not numerically reported here | Different task and outcome; not comparable to classifier accuracy/FPR |

## Removal and evasion

Test-split exact injected-string absence after sanitization: {rm['injected_strings_removed']}/{rm['injected_rows']} ({rm['injected_string_removal_fraction']:.1%}); estimated clean character false removal: {rm['clean_character_false_removal_fraction']:.2%}; mean residual classifier score: {rm['residual_score_mean']:.3f}. Clean removal is an estimate based on returned spans; it is not a semantic preservation metric.

The separate generated transform suite has {ev['suite_size']} cases. Recall: classifier raw {ev['recall']['classifier_before']:.3f}; classifier after normalization {ev['recall']['classifier_after_normalizer']:.3f}; ensemble raw {ev['recall']['ensemble_before']:.3f}; ensemble after normalization {ev['recall']['ensemble_after_normalizer']:.3f}. Remaining ensemble misses after normalization: **{', '.join(ev['remaining_misses']) or 'none'}**. Full per-transform results are in `reports/evasion.json`. Homoglyph and base64 wrapping remain known evasion paths. The built-in obfuscated demo sample is detected and sent through the review sanitizer; this does not establish broad evasion resistance.

## Component checks

`reports/component_assessments.json` separately records scanner example cases, 3 policy boundary cases, and tool authorization cases. The mock executor log contains only allowlisted calls; rejected requests are verified as not executed. These checks demonstrate the demo logic only and do not establish production security.

## Limitations

English-only, text-only, paired 50/50 benchmark; 23 Gemini carriers; the detector misses generated homoglyph and base64 transforms; email false positives remain a concern (see `reports/classifier.json` kind slices). In the frozen classifier result, email FPR was 0.182 and BIPIA-obfuscated recall was 0.23. The current ensemble result and slices are in `reports/ensemble.json`. Attack strings are inserted labels, not successful attacks against an agent. We do not test images/PDFs, browser rendering/DOM, semantic variants comprehensively, downstream agent behavior, or real-world prevalence. Detector and policy results are screening signals, not proof of compromise. This is not production-ready security software.

## Reproduction

From PowerShell in this directory, with Python 3.14:

```powershell
py -3.14 train.py
py -3.14 evaluate.py --all
py -3.14 evasion_eval.py
py -3.14 demo.py
py -3.14 scan.py --ensemble --sanitize demo\\samples\\plain.txt
py -3.14 scan.py --ensemble --sanitize demo\\samples\\hidden.html
py -3.14 demo_app.py
```

The frozen corpus build command is `py -3.14 build_corpus.py --seed 0`; rebuild only when intentionally regenerating the benchmark, then compare `data/manifest.json` and the corpus SHA-256. The baseline and web demo use only the Python standard library and cached local artifacts; no network, API key, or live tool service is required.
'''
(R/'REPORT.md').write_text(report,encoding='utf-8')
