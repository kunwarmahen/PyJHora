# Agentic Tool-Calling Mode for "Ask AI Astrologer"

Status: **implemented** 2026-06-29 (design agreed same day). Backend + frontend
shipped and verified live on Ollama; native function-calling wired for OpenAI-style,
Ollama, **and Gemini** (Gemini live round-trip pending a real key). Remaining
follow-ups (i18n of new strings, tri-state seed, tool-result caching) tracked in
[todo.md §8.9](../todo.md). The sections below describe the design as built; where
the implementation differs it is noted inline.

**Key files:** `web/backend/tools.py` (registry), `web/backend/llm_service.py`
(`run_tool_loop` + per-provider `_chat_once_*` / `_complete_chat`),
`web/backend/main.py` (`/ask` + `/ask/stream` mode branch, `_resolve_mode`,
trace-fetch endpoint), `web/backend/conversations.py` (`mode` field),
`web/backend/tool_traces.py` (lazy full-result side-collection),
`web/frontend/src/services/api.js` (`streamAskQuestion` events + `getConversationTrace`),
`web/frontend/src/pages/AskAstrologerPage.js` (Answer-mode toggle, step pills,
`TraceNode` timeline, lazy `toggleTrace`).

## 1. Motivation

Today the "Ask AI Astrologer" flow is **pass-all**: for every question the
backend eagerly computes a large structured context (D1, dasha chain, yogas,
doshas, transits, ashtakavarga, shadbala, vargas) in
[`chart_context.build_chart_context`](../backend/chart_context.py), flattens it
into one big system prompt in
[`llm_service._render_context_block`](../backend/llm_service.py), and streams the
answer. The user already has coarse control via `sections` toggles + a varga
multi-select.

The proposal: add a second **tool-call (agentic)** mode where we **publish our
compute functions as tools** to the model. The model decides what extra data a
given question needs, emits a tool call, we execute it against `AstrologyCompute`
and feed the result back, looping until it produces the prediction. The user can
**toggle between pass-all and tool mode**.

Why it fits this codebase well: `AstrologyCompute`'s methods are already
stateless, dict-returning, and keyed on the same birth-details args — they map
almost 1:1 onto tool definitions, so the new surface area is thin wrappers, not
new astrology logic.

### Pass-all vs tool-call — trade-offs

| | Pass-all (today) | Tool-call (new) |
|---|---|---|
| Prompt size | Large, fixed every turn | Small seed + only what's fetched |
| Round-trips | 1 | 1 + N tool rounds |
| Who picks data | User (section toggles) | The model, per question |
| Reliability | High (no tool support needed) | Depends on model's tool-calling |
| Best for | Broad "read my chart" asks | Targeted asks ("when do I marry?") |

## 2. Decisions (owner, 2026-06-29)

1. **Provider support — native + JSON fallback.** Use real function-calling on
   providers/models that support it (OpenAI, Gemini, capable Ollama /
   OpenAI-compatible models). For models *without* native tool-calling, run a
   **prompt-based JSON tool-protocol** loop (instruct the model to emit a JSON
   `{"tool": ..., "args": {...}}` object; we parse, execute, and feed results
   back as text). One internal tool-loop abstraction; only the provider edge
   differs.
2. **Baseline seed — configurable, default natal + running dasha.** Always seed
   the natal chart (the base). `dasha_tree` seeded by default. Everything else
   defaults to a **tool** the model can call. The seed set is **user-selectable
   by reusing the existing `sections` toggles + varga selector**: in tool mode a
   section toggled *on* is pre-computed & seeded; *off* means it's exposed as a
   tool. This lets us A/B what helps and refine later (possible future: explicit
   tri-state seed / tool / off per section).
3. **Mode toggle — per-conversation.** Chosen when a conversation starts, stored
   on the conversation doc. Default remains **pass-all** until tool mode proves
   reliable in practice.

## 3. Tools to publish

Thin JSON-schema wrappers over existing `AstrologyCompute` statics. All take the
conversation's birth details (`dob`, `tob`, `place`, `lat`, `lon`, `tz`) +
`ayanamsa` implicitly (injected by the backend, **not** model-supplied), so the
model only supplies the genuinely free parameters.

| Tool name | Backend method | Model-supplied args |
|---|---|---|
| `get_natal_chart` | `calculate_birth_chart` | — |
| `get_dasha_chain` | `get_dashas` (+ `_running_dasha_chain`) | `dhasa_type?` |
| `get_dasha_children` | `get_dasha_children` | `lords_path` |
| `get_yogas` | `get_yogas` | — |
| `get_doshas` | `get_doshas` | — |
| `get_transits` | `get_transits` | — |
| `get_ashtakavarga` | `get_ashtakavarga` | — |
| `get_shadbala` | `get_shadbala` | — |
| `get_chart_details` | `get_chart_details` | — |
| `get_divisional_chart` | `calculate_divisional_chart` | `varga_factor` |
| `get_panchanga` | `get_panchanga` | `date?` |

Design rules:
- **Birth details + ayanamsa are server-injected**, never trusted from the model
  — the model can't ask about a different person.
- Each tool returns the same compact, token-budgeted shape the context renderer
  already produces (reuse the per-section formatting in `_render_context_block`
  so a tool result reads the same whether seeded or fetched).
- Names are stable and descriptive; the JSON-protocol fallback validates the
  model's chosen name against this registry and rejects unknowns.

## 4. Backend architecture

### 4.1 Tool registry (`tools.py`, new)
A single source of truth: for each tool, `{name, description, json_schema,
handler}`. `handler(birth_details, ayanamsa, **model_args) -> dict`. Exposes:
- `tool_specs()` → list of provider-neutral specs (name/description/params) used
  to build native `tools=` payloads **and** the JSON-protocol instructions.
- `dispatch(name, args, birth_details, ayanamsa)` → executes one call, with name
  validation and arg coercion.

### 4.2 Tool loop (`llm_service`)
A provider-agnostic `run_tool_loop(messages, cfg, tools, on_event)`:
1. Send messages (+ tools) to the provider.
2. If the response contains tool call(s): emit a `tool_call` event, run
   `dispatch`, append the tool result message, loop.
3. If it's a final answer: stream/return it.
4. **Guards:** `MAX_TOOL_ROUNDS` (e.g. 6) cap; on repeated invalid/looping calls,
   abort the loop and **fall back to a single pass-all completion** so the user
   always gets an answer.

Per-provider edges:
- **OpenAI / OpenAI-compatible:** native `tools` + `tool_calls` in the delta;
  reuse the existing `_stream_openai_style` plumbing, add tool-call assembly.
- **Gemini:** native via `_chat_once_gemini` — `tools:[{functionDeclarations}]` +
  `toolConfig.functionCallingConfig`, parse `functionCall` parts, feed results back as
  `functionResponse` parts in a **user** turn (consecutive results merged into one turn
  per Gemini's adjacency rule). A schema sanitizer keeps only Gemini-accepted keys
  (drops `default`) and omits empty `parameters`. `id`s echoed when present (parallel
  calls).
- **Ollama:** native `tools` for models that support it; otherwise the JSON
  fallback.
- **JSON fallback (any model):** system instruction tells the model to reply with
  **only** a JSON object `{"tool": "...", "args": {...}}` to request data, or
  prose to answer. We parse each turn; valid JSON → execute & feed back; prose →
  treat as the final answer.

### 4.3 Seeding
In tool mode, build the seed by running `build_chart_context` with **only the
toggled-on sections** (natal always; `dasha_tree` default on; others off →
tools). Render the seed with the existing `_render_context_block` and add a line
telling the model it may call tools for anything not shown.

### 4.4 Endpoint wiring
`/api/astrology/ask` and `/ask/stream` branch on the conversation's `mode`:
- `mode == "pass_all"` (default): unchanged.
- `mode == "tools"`: run `run_tool_loop`. In the streaming endpoint, emit new SSE
  event types alongside `token`:
  - `tool_call` `{name, args}` — "🔧 looking up your dasha…"
  - `tool_result` `{name, ok, result}` — carries the **full returned data** so the
    transcript can show what each call fetched (not just that it ran).
  Persistence uses a **lazy side-collection** so threads stay light: the assistant
  message keeps only the *light* trace (`tool_trace` = name/args/ok) plus an opaque
  `trace_id`; the **full per-call results** go in a separate `ai_tool_traces`
  collection (`tool_traces.py`), keyed by `trace_id`, fetched lazily via
  `GET /api/ai/conversations/{id}/traces/{trace_id}` only when the user expands
  "Behind the scenes" on a reopened answer. Live answers show full data straight
  from the SSE stream (no extra storage). Traces are user-scoped and deleted with
  their conversation.

The conversation doc gains a `mode` field (default `pass_all`) plus, per assistant
message, the light `tool_trace` + `trace_id`.

## 5. Frontend

- **Per-conversation mode toggle** on `AskAstrologerPage` (set at new-conversation
  time; locked once the thread has an AI turn). Persist last choice in
  `localStorage` as the default for the next new conversation. User-facing labels:
  pass-all = **"Full context"**, tools = **"Smart lookup"** (the layman-friendly
  name for tool-call mode).
- In tool mode, render **tool-call step pills** inline in the transcript, plus a
  **"▸ Behind the scenes"** toggle that expands a panel listing every call in order
  with its args and the JSON data it returned (live + rebuilt from the saved trace).
- The existing **section toggles + varga selector** are re-labelled in tool mode
  as "seed vs. tool" controls (toggled-on = seeded; off = available as a tool).
- The **"what was sent" inspector** shows the seed **and** the tool trace
  (each call + its returned data) for tool-mode answers.

## 6. Risks & mitigations

- **Weak local models** hallucinate tool names or loop → name validation, round
  cap, fall back to pass-all on repeated failure.
- **Streaming ↔ tool loop interleaving** → stream tokens; when a tool call is
  detected, pause output, run it, resume; surface steps as discrete events.
- **Token cost** of N tool-result rounds vs one pass-all block → measure with the
  existing per-answer usage capture; the seed-selection knob lets us tune.
- **Latency** (extra round-trips, local models slow) → show step events so the
  wait is legible; keep the round cap low.

## 7. Open questions (revisit during build)

- Should `get_divisional_chart` accept the model's `varga_factor` freely, or be
  constrained to `SUPPORTED_VARGAS`? (Lean: constrain + validate.)
- Do we let the model request the *same* tool twice with different args (e.g.
  drilling dasha children) — yes, but the round cap bounds it.
- Caching tool results within a single answer so the model can't burn rounds
  re-fetching identical data.
