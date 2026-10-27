# Agent Trap Scanner handoff

## Project scope

This is a prompt-injection document screening research demo. It is not the AI-authorship detector mentioned in a separate architecture report. Its offline stack includes a dependency-free TF-IDF logistic classifier, interpretable heuristics, windowed word-surprisal scoring, a validation-fitted logistic ensemble, preview-only sanitizer, three-way document policy, and allowlist-first mock tool authorization. Scores are screening signals, not proof of compromise.

## Frozen data and reproducibility

`data/corpus.jsonl` is the active seed-0 corpus: 3,400 rows from 1,700 paired carriers (2,380 train / 510 validation / 510 test). The exact source/corpus hashes and counts are in `data/manifest.json`. The corpus and split assignments were not changed for this work. `agent_trap_bipia/` is separate. The human/LLM source counts in the evaluation are derived from `carrier_source`; BIPIA email/table are grouped under human attribution, with original source slices still broken out. LLM source carrier counts: Qwen 444, GPT-OSS 333, Gemini 23. The Gemini slice is too small for a stable estimate.

From PowerShell in the project root, with Python 3.14:

```powershell
py -3.14 train.py --no-evaluate
py -3.14 evaluate.py --all
py -3.14 evasion_eval.py
py -3.14 demo.py
py -3.14 scan.py --ensemble --sanitize demo\samples\plain.txt
py -3.14 scan.py --ensemble --sanitize demo\samples\hidden.html
py -3.14 demo_app.py
```

Then open <http://localhost:8000>. Ctrl+C stops the server. No network, key, or external service is used. Optional distilgpt2 is loaded only from an existing local cache; the standard fallback is an n-gram model trained only on clean TRAIN text. Per-document features are cached in `cache/ppl.jsonl`.

For an intentional corpus rebuild, use `py -3.14 build_corpus.py --seed 0`, then verify the hashes and counts in `data/manifest.json`. Rebuilding was not needed for the frozen snapshot. `evaluate.py --all` computes all methods on common splits, tunes thresholds and fits the ensemble on validation only, and evaluates the final held-out test configuration once. Do not tune from test metrics.

## Current evidence

See `reports/REPORT.md` for method trade-offs, ablation, baselines, evasion, removal quality, and limitations. `reports/ablation.json` records commit, seed, corpus/model/config hashes, split metrics, carrier-bootstrap intervals, per-source FPR, style/hiding/position slices, and target pass/fail. `reports/component_assessments.json` independently covers sample scanner detection, policy boundaries, and mock tool authorization. Each detector and combination has a separate file under `reports/`.

The measured ensemble passes the requested numeric targets on this benchmark: accuracy 0.851 and FPR 0.035. This does not establish general performance: recall is 0.737, email-slice FPR remains 0.159, the ensemble does not beat the strongest individual method on every metric, and the separate evasion suite still misses homoglyph and base64-wrapped examples. The example obfuscated injection is caught by the heuristic-assisted ensemble and routed to review; that single example is not an evasion guarantee. Test-split sanitization removed 236/255 exact injected strings (92.5%), with an estimated 3.39% of clean characters removed and mean residual classifier score 0.249.

Document policy cutoffs are in `config/document_policy.json`; it allows below the validation-selected ensemble threshold, holds at/above it, and records quarantine at the configured higher score. Quarantine withholds demo content and is not a file operation. `config/tool_allowlist.json` is an explicit allowlist; unauthorized calls are rejected before `MockExecutor.execute`.

## Data, safety, and limitations

English-only, text-only, paired 50/50 labels; 23 Gemini carriers; variable upstream data sizes and licenses; recurrent attack goals; no image/PDF parsing, rendered browser DOM, agent execution, successful-attack outcomes, or realistic class prevalence. In the original frozen classifier baseline, email FPR was 0.182 and BIPIA-obfuscated recall 0.23. No pretrained external injection classifier was run; BIPIA paper results use different tasks and are not directly comparable. No files are deleted or moved by the demo. Review all `raw/` upstream licenses before redistributing those materials. Treat all results as research screening evidence, not production-ready security.


