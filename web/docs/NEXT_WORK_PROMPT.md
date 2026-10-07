# Prompt — pick up the open work on Jyotir AI

Paste everything below the line into a new Claude Code session opened at the repo root
(`PyJHora/`). It is self-contained: it assumes no memory of earlier conversations.

---

You're continuing work on **Jyotir AI**, a Vedic astrology web app in `web/` (FastAPI + MongoDB
backend in `web/backend`, React/CRA frontend in `web/frontend`) built on the PyJHora engine in
`src/jhora`. The owner wants the remaining open work done. Everything that's open is written down in
**`web/todo.md`**: the "Open work" table near the top is the index, and **§85** has the detail for each
item. Treat §85 as the source of truth, not this prompt.

## Before you change anything

1. Read the "Open work" table at the top of `web/todo.md`, then all of **§85**. Skim §83–§84 for the
   most recent context (narrowed Pitru and Mangal rules, Hindi rollout, realistic-payload page harness).
2. Read `web/README.md` and `web/docs/ARCHITECTURE.md` (testing section especially).
3. Anything touching translations: read `web/docs/I18N_DATA_LAYER_DESIGN.md` **first** — it records
   traps that aren't visible in the code (e.g. nakshatra lists only correspond by position).
4. Adding or renaming a page, tab, tool or computation: load the `wire-a-feature` skill and walk its
   checklist (registry, route, AI tool, search, Help/FAQ, i18n, tests, docs).

## What to do, in this order

1. **§85.1 is answered** (Manglik aligned, §86); the Hindi typo and Vite stay parked unless the owner
   raises them.
2. **CI.** Check that `web-ci` is green for the latest pushed commit: `gh run list`, or if `gh` isn't
   installed, `curl -s https://api.github.com/repos/kunwarmahen/PyJHora/actions/runs?per_page=5`. Don't
   push just to trigger it; pushing is the owner's call. If it failed, fix it.
3. **§85.2 translation** is done for Hindi (§88). What's left there is English by design (raja-yoga,
   panchanga, koota names) or deferred (Sanskrit). Any new UI string needs its Hindi in the same change;
   `hindiCoverage.test.js` enforces it. Vocabulary: डाइजेस्ट (digest), पन्ना (page), पाठ (reading).
4. **§85.3 product follow-ups.** For any number that reaches a user, *measure* it with the function the
   page actually uses (pattern: `web/backend/scripts/dosha_prevalence.py`). Never quote a figure from memory.
5. **§85.4 upkeep** as it comes up. **§85.5 hardening** only if its condition has become true.

## How to work here (owner's standing preferences)

- **Work directly on `main`.** No feature branches. Commit each finished slice separately.
- **Never push** unless the owner asks.
- **Never touch the root `.gitignore`.** It has the owner's own uncommitted edits; stage `web/` and
  `.github/` paths only.
- A change isn't done until the **Help/FAQ** says so (`frontend/src/config/help.js` +
  `help.q/a.*` in `en.json`), **`web/docs/FEATURES.md`** is updated, and **`web/todo.md`** has a
  numbered section: what shipped, the traps, the tests. Tick the §85 items you finish and update the
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
