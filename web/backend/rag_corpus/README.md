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
their stated `source`/`reference`. `seed_principles.jsonl` uses the honest
reference **"General principle"** (not a verse number), so it never
misrepresents a classical citation; `brihat_jataka_1885.jsonl` carries real
chapter and verse numbers because they were read off the page.

## What is bundled

| file | passages | reference |
|---|---|---|
| `brihat_jataka_1885.jsonl` | 246 | real — `Ch. 7 v. 3` |
| `seed_principles.jsonl` | 69 | honest — `General principle` |

`brihat_jataka_1885.jsonl` is **Brihat Jataka of Varaha Mihira**, translated by
N. Chidambaram Iyer (Foster Press, Madras, **1885**) — long out of copyright,
scanned by Google, and available from Archive.org as
`brihatjatakavar00iyergoog`. It is generated, never hand-edited:

```bash
curl -L -o bj.txt \
  https://archive.org/download/brihatjatakavar00iyergoog/brihatjatakavar00iyergoog_djvu.txt
python rag_corpus/import_text.py brihat-jataka-1885 \
  --input bj.txt --output rag_corpus/brihat_jataka_1885.jsonl
```

## Adding another text

`import_text.py` holds one **profile** per edition, because every scan is laid
out differently. Add a `Profile` subclass (source name, expected chapter count,
where the front matter ends) and register it in `PROFILES`; `--dry-run` prints
what it would import without writing.

Two rules the importer follows, and any new profile should keep:

- **Headings are authoritative.** A verse is filed under the chapter its printed
  heading says, never under a number inferred from position. Where a heading did
  not survive the scan and the arithmetic is ambiguous, those verses are
  **dropped** — a wrong citation is worse than a missing one. The 1885 Brihat
  Jataka loses 57 stanzas that way, and the run reports the number.
- **An OCR quality gate.** Every candidate is scored by the fraction of its
  words a dictionary recognises and dropped below `--min-quality` (0.85), so a
  garbled line is never quoted as scripture under a real verse number.

`tests/test_rag_corpus.py` guards both, and checks the imported chapters against
the contents list the book prints in its own final chapter.

## Embeddings

Passages are embedded with a local **Ollama** model — no cloud service. Configure:

- `OLLAMA_URL` (default `http://localhost:11434`)
- `RAG_EMBED_MODEL` (default `nomic-embed-text` — `ollama pull nomic-embed-text`)

- `RAG_EMBED_BATCH` (default `16`) — passages per request to Ollama's
  `/api/embed`. Builds that only have the older `/api/embeddings` fall back to
  one request per passage automatically.

The index is cached to `.index.json` (gitignored — it is derived) and rebuilt
automatically when the corpus or model changes. The first build after adding a
book embeds every passage and logs its progress; afterwards it is instant. If
Ollama or the model is unavailable, the feature simply stays off (readings
proceed without citations).
