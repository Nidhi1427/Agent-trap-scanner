# Real carriers (team step)
Generate >=500 clean pages/emails/documents from each of >=3 LLMs (e.g. Claude, GPT, Gemini/Llama) and add human-written ones.
Prompt per item: "Write a realistic {kind} (about 250-500 words, 5+ paragraphs, blank line between paragraphs) about {topic}.
Plain prose only; do NOT include any instructions addressed to an AI." Vary {topic} widely (>=100 topics) and {kind} in web|email|document.
Save as carriers/real/<llm>.jsonl, one JSON per line: {"id","kind","source":"<llm>","topic","text"}  (paragraphs separated by \n\n).
Then: python build_corpus.py   (real carriers are picked up automatically; toy carriers are ignored).
Spot-read ~30 per LLM to make sure none contains instruction-like text, then re-run.
