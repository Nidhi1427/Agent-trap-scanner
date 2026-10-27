# Agent Trap Scanner — technical report

Generated from `reports/ablation.json` on 2026-10-27T07:16:34.785061+00:00. Research demo; all detection thresholds and the ensemble fit use validation data only. The seed-0 corpus hash is `3d3606ee3cc86d6560730f1cedf9143724cc5ec4030aef4931f9f267246acbef`; commit `4fc9dde62198080ffaca1e48596ba6d0249d3bf3`; model SHA-256 `4591b3596b96f56d39d0d15033ff6b4276fe73ccc0bdcbff60a2cf3bba93a529`. Detailed per-detector JSON, bootstrap intervals, and slices are in `reports/`.

## Method and trade-offs

The lexical classifier is a dependency-free TF-IDF unigram/bigram logistic model. The hand-set heuristic layer normalizes selected spaced letters, common leetspeak, zero-width marks, and Unicode compatibility forms; it flags override patterns, imperative density, sensitive targets, and HTML hidden/comment/attribute channels. These rules are inspectable but brittle and can false-positive. The perplexity signal compares 40-token windows using maximum local surprisal against a document median. Backend used: **ngram**. The fallback is a word n-gram model trained from clean TRAIN documents only; local distilgpt2 weights are used only if already cached. Per-document scores are cached in `cache/ppl.jsonl`. This feature is an anomaly signal, not a semantic detector. A logistic stack is fitted on validation scores for the classifier, heuristics, and perplexity. Max-score pairs/all-three are reported as simple ablations. Sanitization removes flagged sentence or hidden-channel text into a returned preview; source documents are never edited. Policy is a separate allow/hold/quarantine layer, and tool authorization checks a named allowlist before the mock executor.

## Data, splits, and benchmark

Frozen active corpus: **3,400 rows / 1,700 paired carriers**, seed 0; train/validation/test sizes are 2,380/510/510. It is paired and 50/50 by construction. Authorship carrier counts are `{"human": 900, "llm:gemini": 23, "llm:groq-gptoss": 333, "llm:groq-qwen": 444}` (BIPIA email/table are grouped as human for this source attribution; they remain separate in carrier-source slice reports). LLM sources include Qwen, GPT-OSS, and Gemini; Gemini has only 23 carriers, so the source slice is not stable. The older `agent_trap_bipia/` dataset is excluded.

Thresholds were selected on validation to keep FPR strictly below 10%; test scores are reported once for the final configuration. Bootstrap intervals resample carrier IDs to preserve clean/injected pairs. **Ensemble test accuracy 0.851; FPR 0.035; recall 0.737; AUROC 0.935.** Accuracy target ≥0.85: PASS. FPR target <0.10: PASS.

## Ablation and baselines

| Method | Accuracy | FPR | Recall | Precision | AUROC | TPR@5% FPR |
|---|---:|---:|---:|---:|---:|---:|
| classifier | 0.861 [0.827, 0.890] | 0.055 | 0.776 | 0.934 | 0.935 | 0.749 |
| heuristics | 0.592 [0.569, 0.618] | 0.031 | 0.216 | 0.873 | 0.632 | 0.180 |
| perplexity | 0.537 [0.520, 0.555] | 0.063 | 0.137 | 0.686 | 0.527 | 0.106 |
| keyword | 0.639 [0.610, 0.665] | 0.012 | 0.290 | 0.961 | 0.640 | 0.290 |
| classifier+heuristics | 0.861 [0.827, 0.890] | 0.055 | 0.776 | 0.934 | 0.936 | 0.741 |
| classifier+perplexity | 0.849 [0.816, 0.875] | 0.051 | 0.749 | 0.936 | 0.930 | 0.749 |
| heuristics+perplexity | 0.602 [0.575, 0.627] | 0.063 | 0.267 | 0.810 | 0.615 | 0.247 |
| all_three | 0.849 [0.816, 0.875] | 0.051 | 0.749 | 0.936 | 0.930 | 0.745 |
| ensemble | 0.851 [0.818, 0.878] | 0.035 | 0.737 | 0.954 | 0.935 | 0.737 |

The ensemble does **not** beat the best single detector on every measure: classifier accuracy is 0.861 versus ensemble 0.851; classifier AUROC is 0.935 versus ensemble 0.935. Keyword baseline on the same test set: accuracy 0.639, FPR 0.012, recall 0.290, AUROC 0.640. An external pretrained classifier was **not run**; no weights were downloaded. BIPIA reports model attack outcomes and defense effectiveness on different tasks and cannot be compared numerically to this text-classification accuracy/FPR; no paper score is copied. See [Yi et al., BIPIA, arXiv:2312.14197](https://arxiv.org/abs/2312.14197).

| Baseline | Same test set? | Result | Interpretation |
|---|---|---|---|
| Keyword rules | Yes | accuracy 0.639; FPR 0.012; recall 0.290; AUROC 0.640 | Simple lexical reference |
| External pretrained injection classifier | No | Not run | Optional model package/weights were unavailable locally; no network download attempted |
| BIPIA paper (Yi et al.) | No | Not numerically reported here | Different task and outcome; not comparable to classifier accuracy/FPR |

## Removal and evasion

Test-split exact injected-string absence after sanitization: 236/255 (92.5%); estimated clean character false removal: 3.39%; mean residual classifier score: 0.249. Clean removal is an estimate based on returned spans; it is not a semantic preservation metric.

The separate generated transform suite has 7 cases. Recall: classifier raw 0.714; classifier after normalization 0.857; ensemble raw 0.714; ensemble after normalization 0.857. Remaining ensemble misses after normalization: **base64_wrapped**. Full per-transform results are in `reports/evasion.json`. Homoglyph and base64 wrapping remain known evasion paths. The built-in obfuscated demo sample is detected and sent through the review sanitizer; this does not establish broad evasion resistance.

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
py -3.14 scan.py --ensemble --sanitize demo\samples\plain.txt
py -3.14 scan.py --ensemble --sanitize demo\samples\hidden.html
py -3.14 demo_app.py
```

The frozen corpus build command is `py -3.14 build_corpus.py --seed 0`; rebuild only when intentionally regenerating the benchmark, then compare `data/manifest.json` and the corpus SHA-256. The baseline and web demo use only the Python standard library and cached local artifacts; no network, API key, or live tool service is required.
