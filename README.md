# Agent Trap Scanner: prompt-injection corpus and evaluation

This folder contains a dataset and baseline harness for detecting prompt-injection text in documents an agent may read. It does **not** implement the AI-generated-text detector described by the separate architecture report at the workspace root.

## Source of truth

`data/corpus.jsonl` is the active benchmark. It is generated from the carrier files in `carriers/real/` plus BIPIA email/table carriers, with one clean and one injected document per carrier. `agent_trap_bipia/` is a separate, older BIPIA-only packaged dataset; do not mix its files into this benchmark's splits or metrics.

Regenerate the corpus from this directory with:

```powershell
py -3.14 build_corpus.py --seed 0
```

The build uses Python's standard library only. The seed, sorted carrier input files, and shared benign HTML snippets make the paired corpus repeatable. Change the seed only when intentionally creating a new dataset version.
`data/manifest.json` records the seed, split counts, and SHA-256 hashes for the corpus, source data, and build scripts.

Create slim training/evaluation files and a datasheet with:

```powershell
py -3.14 export_dataset.py
```

This writes `export/train.jsonl`, `export/val.jsonl`, `export/test.jsonl`, plus separate `test_ood.jsonl` and `evasion_test.jsonl` files. Each also has a `_full.jsonl` version with metadata and raw HTML.

## Current corpus snapshot

Generated with seed `0` on 2026-10-17:

| Split | Carriers | Clean | Injected | Total rows |
|---|---:|---:|---:|---:|
| Train | 1,190 | 1,190 | 1,190 | 2,380 |
| Validation | 255 | 255 | 255 | 510 |
| Test | 255 | 255 | 255 | 510 |
| **Total** | **1,700** | **1,700** | **1,700** | **3,400** |

Clean carrier sources: 500 Wikipedia, 444 Groq Qwen, 333 Groq GPT-OSS, 300 BIPIA table, 100 BIPIA email, and 23 Gemini documents. Carrier kinds: 860 web pages, 351 emails, 300 tables, and 189 documents. This is a deliberately balanced benchmark, not a representative estimate of real-world prevalence.

Injected styles include Open-Prompt-Injection strategies, InjecAgent instructions, wrapped Garak/agent instructions, and BIPIA text/code attacks. `authority_notice` and `bipia_obfuscated` are test-only styles. The test-only notice style reuses attack goals from InjecAgent, so this measures new framing more than unseen intent. No exact injected string is assigned to more than one split. Each carrier's clean and injected pair stays in the same split.

For web carriers, injected instructions can be placed in visible text, HTML comments, CSS-hidden text, zero-size text, white-on-white text, or selected attributes. Extraction returns candidate text from these channels for scoring, so the benchmark tests text scanning, not browser rendering or actual agent behavior.

## Evaluation

Train the TF-IDF logistic baseline and select its operating threshold from validation data:

```powershell
py -3.14 train.py
```

This writes `models/agent_trap_model.json`, then reports test AUROC, average precision, thresholded metrics, slice rates, and 95% carrier-cluster bootstrap intervals. The threshold is selected on validation data to maximize accuracy subject to the configured FPR bound (10%), then held fixed for test evaluation. The bootstrap resamples carrier IDs so each clean/injected pair remains together.

Scan a text file or HTML file (HTML extensions are parsed automatically):

```powershell
py -3.14 scan.py sample.txt
py -3.14 scan.py page.html
Get-Content sample.txt -Raw | py -3.14 scan.py
```

The scanner returns JSON with a score, threshold, label, and top feature contributions. `possible_injection` means the text crossed the selected threshold; `no_match` does not prove that content is safe. HTML scanning extracts text, comments, selected attributes, and inline-style hidden content, but does not render a browser DOM or execute scripts.

The seed-0 test run for this corpus achieved 0.935 AUROC, 0.776 recall, and 0.055 FPR. Performance varied by slice: recall was 0.23 on BIPIA obfuscations, and the email slice had 0.182 FPR. These are benchmark results from this dataset, not deployment guarantees; the Gemini test slice has only three clean carriers and is too small for a stable source-specific estimate.

For a custom scanner, implement a function that takes a list of strings and returns one numeric score per string (higher means more likely injected), then pass it to `evaluate.evaluate`.

## Offline policy and authorization demo

Run `py -3.14 demo.py` for a fully offline walkthrough with four sample documents and three mock tool requests. Inputs are in `demo/`; they are independent of the benchmark. Detailed results are written to `reports/demo_results.json`. The frozen model detects the obvious and hidden-HTML examples, allows the benign note, and misses the obfuscated example; this miss is intentional evidence of the baseline's limitation. The demo separately assesses scanner detection, the document policy, and tool authorization.

`policy.py` applies configurable allow, hold-for-review, and quarantine decisions using `config/document_policy.json`; its result preserves the raw score. Quarantine is recorded only and does not move or delete files. `tool_auth.py` uses the explicit `config/tool_allowlist.json`; unauthorized requests are rejected before the mock executor. The demo verifies that only the allowlisted tool reaches that executor. These are independent checks: detector performance does not establish policy correctness or authorization safety.

See [HANDOFF.md](HANDOFF.md) for method, data and splits, frozen metrics, limitations, and fresh-terminal instructions. The saved evaluation is in `reports/frozen_evaluation.txt`.

## Known limitations

- The corpus is English-only and uses text carriers; it does not cover images, PDFs, browser DOM behavior, or whether an agent actually follows the injection.
- Positive labels mean an attack string was inserted, not that it successfully changed an agent's behavior or caused harm. Attack categories differ in intent and should not be collapsed into a claim about successful compromise.
- The current carrier set is small and imbalanced by source. In particular, the Gemini source has only 23 examples; source-specific rates for it are not stable.
- Attack goals recur across attack styles. The held-out style scores do not establish generalization to wholly novel attack objectives.
- The corpus is paired and 50/50 by design. Precision and F1 from it do not estimate deployment performance without a realistic class prevalence.
- Exact-string splitting prevents direct string reuse across splits, but paraphrases and semantically similar instructions can still cross splits.
- `raw/` contains upstream benchmark code/data with their own licenses. Review those licenses before redistribution; the BIPIA MIT notice does not cover every dataset bundled under its benchmark directory.
