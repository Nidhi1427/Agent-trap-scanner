# Agent Trap Scanner dataset datasheet

Task: binary text-level screening for an inserted prompt-injection string (1) versus its clean carrier (0). A positive label does not mean an agent followed the string or that harm occurred.

| file | clean | injected | rows |
|---|---:|---:|---:|
| evasion_test.jsonl | 35 | 35 | 70 |
| test.jsonl | 185 | 185 | 370 |
| test_ood.jsonl | 35 | 35 | 70 |
| train.jsonl | 1190 | 1190 | 2380 |
| val.jsonl | 255 | 255 | 510 |

Carrier sources: BIPIA-email=100, BIPIA-table=300, gemini=23, groq-gptoss=333, groq-qwen=444, wikipedia-human=500
Carrier kinds: document=189, email=351, table=300, web=860
Attack sources: BIPIA=687, InjecAgent=315, InjecAgent+team-wrappers=304, Open-Prompt-Injection=338, garak+team-wrappers=21, team-authored=35

Use train.jsonl for fitting and validation.jsonl for tuning. Keep test.jsonl, test_ood.jsonl, and evasion_test.jsonl for final evaluation. Carrier pairs stay in a single split; exact injected strings are not reused across splits.
test_ood.jsonl holds out the team-authored authority_notice framing; its underlying attack goals are reused from InjecAgent. evasion_test.jsonl contains BIPIA obfuscation categories. These are limited held-out settings, not proof of generalization to every unseen attack.
The corpus is English-only, text-only, and balanced by construction. Precision/F1 do not estimate deployment performance without a realistic prevalence. Source datasets have separate licenses; review each upstream license before redistribution.
