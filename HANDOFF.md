# Agent Trap Scanner handoff

## Purpose and method

This repository is a prompt-injection text screening research demo. Its baseline is a dependency-free TF-IDF unigram/bigram logistic model. The validation split selects a score threshold under a target FPR bound; the test split is held out. HTML scanning extracts candidate text, including comments, selected attributes, and CSS-hidden text, without rendering or executing a browser page. A positive result is a screening signal, not proof of compromise.

The document policy is a separate layer in `policy.py`, configurable in `config/document_policy.json`. The current demonstration holds documents at or above 0.373 for review and records a quarantine decision at or above 0.75. The score remains separately reported. Quarantine in this demo is only a recorded decision; it never alters real files. Tool authorization is separate as well: `tool_auth.py` checks the explicit `config/tool_allowlist.json` allowlist before invoking the recording `MockExecutor`. There is no live agent tool runner.

## Data and splits

`data/corpus.jsonl` is the only active benchmark: 3,400 rows across 1,700 paired carriers. Seed 0 yields train 2,380 (1,190 clean and 1,190 injected), validation 510 (255/255), and test 510 (255/255). The manifest is `data/manifest.json`; it records the seed, counts, and input/corpus hashes. `agent_trap_bipia/` is a separate older package and is excluded from these numbers. Demo examples under `demo/` are also separate from benchmark inputs. Upstream material under `raw/` has varied licenses; review each source's license before redistribution.

## Frozen-model evaluation

Recorded by rebuilding seed 0 and running `py -3.14 train.py` on 2026-10-25. Model threshold selected on validation: 0.373. Full console output and slice metrics are in `reports/frozen_evaluation.txt`.

| Test metric | Result (95% carrier-bootstrap interval) |
|---|---:|
| AUROC | 0.935 [0.915, 0.953] |
| Recall | 0.776 [0.722, 0.824] |
| FPR | 0.055 [0.031, 0.086] |
| Precision | 0.934 [0.901, 0.962] |
| Accuracy | 0.861 [0.831, 0.886] |

Key slice results: email FPR 0.182 (8/44 clean); web FPR 0.043 (6/139); table FPR 0/50; document FPR 0/22. BIPIA-obfuscated recall is 0.23 (8/35); BIPIA text recall is 0.29 (10/34). The Gemini source has only three clean test carriers. These slices are small and must not be treated as stable operating rates. No test-split tuning was performed.

## Component assessments

Run `py -3.14 demo.py` for an offline end-to-end demo; its complete per-input results are saved to `reports/demo_results.json`.

- **Scanner detection:** four distinct examples (benign text, direct injection, hidden HTML injection, and obfuscated injection) are evaluated against the frozen scanner threshold. Each individual predicted label and expected label is recorded. This small smoke sample does not estimate detector quality; obfuscation may evade the lexical baseline.
- **Document policy:** three independent synthetic scores exercise allow, hold-for-review, and quarantine. Results are recorded separately from scanner evaluation.
- **Tool authorization:** one allowlisted request and two unauthorized requests are checked. The mock executor's call log must contain only `lookup_public_help`; rejected requests report `executor_called: false`.

## Reproduce from a fresh terminal

Requires Python 3.14 and no third-party packages or network access. Open a terminal in this directory:

```powershell
py -3.14 build_corpus.py --seed 0
py -3.14 train.py
py -3.14 scan.py demo\samples\plain.txt
py -3.14 scan.py demo\samples\hidden.html
py -3.14 demo.py
```

Build the active corpus before training. Training writes `models/agent_trap_model.json` and prints evaluation results. To save a fresh evaluation log, run `py -3.14 train.py *> reports/frozen_evaluation.txt`. Plain text and HTML CLI examples are in `demo/samples/`. `scan.py` accepts HTML by extension or `--html`; stdin is also supported. Policy thresholds and tool allowlist are ordinary JSON configuration files. No API keys, network calls, or external services are used.

## Limitations

This corpus is English-only, text-only, paired, and balanced by construction. It does not test whether an agent follows an injected instruction, actual impact, images/PDFs, browser DOM/rendering, or novel attack goals. Precision and F1 do not represent production prevalence. Source sizes vary, and slices can be small. Exact-string separation does not prevent semantic overlap. Detector scores and policy outcomes are screening signals, not proof. This is a reproducible research demo, not production-ready security software.
