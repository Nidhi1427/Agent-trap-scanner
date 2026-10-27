# Agent Trap Scanner

An offline research demo for screening prompt-injection text in documents. This is the prompt-injection scanner project, not the separate AI-authorship detector described in an architecture report.

## Current reproducible state

- Active benchmark: `data/corpus.jsonl`, 3,400 rows / 1,700 paired carriers, seed 0; frozen splits are train 2,380, validation 510, test 510. `data/manifest.json` is the authoritative manifest. Do not mix the older `agent_trap_bipia/` package into its metrics.
- Scanner stack: existing dependency-free TF-IDF logistic classifier, interpretable heuristics, and a 40-token local-surprisal feature using clean TRAIN-only word n-grams by default. Cached local `distilgpt2` is optional; no model is downloaded. A logistic ensemble is fitted only on validation data.
- `reports/ablation.json`, `reports/REPORT.md`, and per-detector JSON are generated evidence. The demo reads these files instead of hardcoding test metrics.
- The app and CLI are offline. Detector and policy outputs are screening signals, not proof. Sanitization returns a preview and does not modify source files. Quarantine is recorded/withheld only. Tool requests pass an explicit allowlist before a recording mock executor.

## PowerShell: run from a fresh terminal

```powershell
Set-Location 'C:\Users\Nidhi\Downloads\CPI\CPI\CPI dataset\CPI dataset'
py -3.14 train.py --no-evaluate
py -3.14 evaluate.py --all
py -3.14 evasion_eval.py
py -3.14 demo.py
py -3.14 scan.py --ensemble --sanitize demo\samples\plain.txt
py -3.14 scan.py --ensemble --sanitize demo\samples\hidden.html
py -3.14 demo_app.py
```

Open <http://localhost:8000>. Stop the server with Ctrl+C. The standard-library path requires no install, API key, or network. Optional transformer support uses only local model weights; otherwise the clean-train n-gram implementation runs. `cache/` contains regenerable per-document scores.

To rebuild the corpus intentionally, run `py -3.14 build_corpus.py --seed 0` and compare `data/manifest.json` and SHA-256 before accepting the new snapshot. This demo work did not alter the corpus or split assignment. To reproduce final metrics, run training first, then `evaluate.py --all`; the harness chooses thresholds and fits the stack on validation and reports the held-out test once for that final configuration. Do not choose parameters using the test report.

## Reports and configuration

- `reports/REPORT.md`: short technical report and honest result/limitation summary.
- `reports/ablation.json`, `reports/{classifier,heuristics,perplexity,ensemble,keyword}.json`: common test evaluation, bootstrap confidence intervals and slices.
- `reports/evasion.json`: generated transform suite, separate from benchmark.
- `reports/component_assessments.json`: independent scanner, policy, and authorization checks.
- `config/detector_thresholds.json`: validation-selected detector and ensemble thresholds. `config/heuristics.json`, `config/perplexity.json`, and `config/document_policy.json` document editable rules and workflow cutoffs. `config/tool_allowlist.json` controls mock authorization.

## Known limitations

The corpus is English-only, text-only, paired, and balanced 50/50. There are only 23 Gemini carriers. The classifier baseline had email FPR 0.182 and BIPIA-obfuscated recall 0.23; the new ensemble still has elevated email-slice FPR (see reports). The generated evasion suite still demonstrates homoglyph and base64 misses. Removal has measurable false-removal cost. The stack does not validate downstream agent behavior or prove compromise resistance. This is a reproducible research demo, not production-ready security. Upstream material in `raw/` has multiple licenses; review upstream notices before redistribution.


