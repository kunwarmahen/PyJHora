# Prompt — pick up the open work on Jyotir AI

Paste everything below the line into a new Claude Code session opened at the repo root
(`PyJHora/`). It is self-contained: it assumes no memory of earlier conversations.

---

You're continuing work on **Jyotir AI**, a Vedic astrology web app in `web/` (FastAPI + MongoDB
backend in `web/backend`, React/CRA frontend in `web/frontend`) built on the PyJHora engine in
`src/jhora`. The owner wants the remaining open work done. Everything that's open is written down in
**`web/todo.md`**: the "Open work" table near the top is the index, and **§82** has the detail for each
item. Treat §82 as the source of truth, not this prompt.

## Before you change anything

1. Read the "Open work" table at the top of `web/todo.md`, then all of **§82**. Skim §79–§81 for the
   most recent context (hubs, docs split, the page-mount test harness, newcomer onboarding).
2. Read `web/README.md` and `web/docs/ARCHITECTURE.md` (testing section especially).
3. Anything touching translations: read `web/docs/I18N_DATA_LAYER_DESIGN.md` **first** — it records
   traps that aren't visible in the code (e.g. nakshatra lists only correspond by position).
4. Adding or renaming a page, tab, tool or computation: load the `wire-a-feature` skill and walk its
   checklist (registry, route, AI tool, search, Help/FAQ, i18n, tests, docs).

## What to do, in this order

1. **Ask the owner the four §82.1 decisions in one go** (AskUserQuestion), with a recommendation for
   each:
   - Pitru Dosha (fires for 88.8% of charts): keep, narrow, or hide?
   - New screens are English-only: is that the steady state, or should they be translated (Hindi first)?
   - The Hindi typo `म्रृगशीर्षा`: patch the upstream file, or add an override?
   - Vite migration: still optional now that the page harness exists. Do it?

   Don't start an item that depends on an answer before you have it.
2. **§82.2 — CI.** Check whether `.github/workflows/web-ci.yml` has run (`gh run list`). If it hasn't,
   say so; don't push just to trigger it. Pushing is the owner's call. If it has run and failed, fix it.
3. **§82.3 translations** and **§82.4 product gaps**, as far as the answers allow. Notes:
   - For Mangal-dosha prevalence on Compatibility, *measure* it with the function that tab actually uses
     (pattern: `web/backend/scripts/dosha_prevalence.py`). Never quote a figure from memory.
   - New Topic Reading topics need a prompt entry in `llm/prompts.py` `_build_prediction_prompt` before
     the page offers them.
4. **§82.5 hardening**, if time remains. The realistic-payload mode for the page harness is the most
   valuable of these.

## How to work here (owner's standing preferences)

- **Work directly on `main`.** No feature branches. Commit each finished slice separately.
- **Never push** unless the owner asks.
- **Never touch the root `.gitignore`.** It has the owner's own uncommitted edits; stage `web/` and
  `.github/` paths only.
- A change isn't done until the **Help/FAQ** says so (`frontend/src/config/help.js` +
  `help.q/a.*` in `en.json`), **`web/docs/FEATURES.md`** is updated, and **`web/todo.md`** has a
  numbered section: what shipped, the traps, the tests. Tick the §82 items you finish and update the
  index table at the top.
- `web/docs/` is git-ignored except for an allow-list in `web/.gitignore`. A new doc must be added there,
  or it never reaches git.
- Measure, don't assert. When a number reaches a user (a prevalence, a date, a count), compute it with
  the app's own code and pin it with a test.

## Running and checking

```bash
cd web
./dev.sh test                         # backend (~1,200 tests); or: cd backend && venv/bin/python -m pytest tests -q
cd frontend && CI=true npx react-scripts test --watchAll=false   # ~525 tests, incl. every page mounted
npx eslint src --max-warnings=0 && npx prettier --check "src/**/*.{js,css}"
```

- The backend has **no auto-reload**. Run `./dev.sh restart backend` after editing any `.py` before
  testing in the browser.
- Drive the real UI with the `verify` skill (Playwright in a scratch venv). The owner's reference chart
  is 1976-06-04 05:45:02, Shahgarh/Aligarh (27.845, 78.334, +5.5).
- If a Jest run hangs, kill node directly: `timeout -s KILL 600 node node_modules/.bin/react-scripts test …`.
  A `timeout` on `npx` doesn't reach node. Also, `pgrep -f` patterns can match your own shell.
- In the page harness (`src/pages/pages.smoke.test.js`), context stubs must be *stable objects*, and
  stubbed functions must be plain functions, not `jest.fn` (CRA's `resetMocks`). The file explains why.

## When you finish

Report to the owner in plain language: what shipped (with commit hashes), what you measured or
verified and how, what you deliberately left, and any new decisions for them. Every open item must
end up in `web/todo.md`, not only in your message.
