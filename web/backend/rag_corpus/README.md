# Classical-text corpus (RAG, §5.12)

The AI can ground its readings in a local corpus of classical Jyotish passages and
**cite** them, instead of asserting on its own authority. This folder holds that
corpus. Retrieval + embeddings live in `../rag.py`.

## Format

One JSON object per line, in any `*.jsonl` file here:

```json
{"source": "BPHS", "reference": "Ch.24 v.13", "text": "…the translated passage…"}
```

- `source` — the work (e.g. `BPHS`, `Saravali`, `Phaladeepika`, `Jataka Parijata`).
- `reference` — chapter/verse or section, shown in the citation. **Only use a real
  reference for real text.** Never attach a verse number to a paraphrase.
- `text` — the passage the AI retrieves and cites (one idea per line reads best).

Lines beginning with `#` are comments and are ignored.

## Integrity

`rag.py` invents nothing — it returns only passages present in these files, with
their stated `source`/`reference`. The bundled `seed_principles.jsonl` uses the
honest reference **"General principle"** (not a verse number), so it never
misrepresents a classical citation. Replace or extend it with **genuinely
public-domain** translations (e.g. out-of-copyright editions) that carry real
references to get real shloka citations.

## Embeddings

Passages are embedded with a local **Ollama** model — no cloud service. Configure:

- `OLLAMA_URL` (default `http://localhost:11434`)
- `RAG_EMBED_MODEL` (default `nomic-embed-text` — `ollama pull nomic-embed-text`)

The index is cached to `.index.json` and rebuilt automatically when the corpus or
model changes. If Ollama or the model is unavailable, the feature simply stays
off (readings proceed without citations).
