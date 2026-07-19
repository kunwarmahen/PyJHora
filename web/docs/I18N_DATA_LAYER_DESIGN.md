# Localizing engine-returned data (the i18n "data layer")

Status: **in progress** — machinery + BirthChart + yogas shipped 2026-07-16; ~22 files
still to wrap. Tracked as web/todo.md §5 P3, which links here rather than repeating it.
This is the durable record: the decisions, the traps, and what a future session needs to
resume without re-deriving any of it.

Related: `web/todo.md` §5 (task list), `web/improvements-2026-07.md` §4 (the backend split
that this work sits on top of).

---

## 1. The problem

The UI *chrome* has been fully translated (en/hi/sa) since 2026-06-29. But the **values**
that come back from the backend were all English, so switching to Hindi produced a
half-translated page: Hindi labels wrapped around `Moon in Krittika, Aries ascendant`,
`Amala Yoga`, `Kala Sarpa Dosha`.

Two different kinds of string are involved, and they have different answers:

| Kind | Examples | Who can translate it |
|---|---|---|
| **Fixed enumerations** | 12 rasis, 27 nakshatras, 9 grahas, dasha lords, panchanga limbs | frontend mapping (A) |
| **Engine free text** | yoga/raja-yoga/dosha names + descriptions, predictions | PyJHora only (B) |

Nothing translates the second kind except PyJHora — a frontend lookup table cannot
invent a paragraph. And nothing translates *Sanskrit* except us — PyJHora has no `sa`
resources at all. Hence the outcome is a **hybrid**, not one path.

## 2. The decision

**A (frontend mapping) owns the enumerations. B (PyJHora's language support) owns the
engine free text. Sanskrit routes to Hindi wherever B is involved.**

Decided 2026-07-16 with the owner. The sa→hi routing was the owner's explicit call: for a
Sanskrit reader, Hindi shares the script and most of this vocabulary, so it lands far
closer than English. It is a **stopgap, not the destination** — see §6 open items.

### Why not B for everything?

- PyJHora ships `en/ta/te/hi/ka/ml` only. **No Sanskrit.** `sa` users would silently get
  English for everything.
- The chart-name tables would need the *global* `utils.set_language()` (see the trap in
  §4.2) plus a backend refactor off its own hardcoded `ZODIAC_NAMES` / `nakshatra_names`.

### Why not A for everything?

- It structurally cannot do free text. The yoga cards are the biggest block of English on
  the birth chart and A can never touch them.

## 3. What shipped (2026-07-16)

### 3.1 The A layer — `frontend/src/i18n/localizeName.js`

- `localizeName(name, kind, lang, {abbr})` + `useLocalizeName()` hook.
  `kind` is `rasi` | `nakshatra` | `graha`.
- Tables are **generated**, not hand-written: `frontend/scripts/gen-name-locales.js`
  (`npm run gen:names`) → `frontend/src/constants/nameLocales.generated.js`.
  Hindi is read from `src/jhora/lang/list_values_hi.txt` so it tracks upstream.
- Everything upstream can't supply is hand-authored in
  `frontend/scripts/name-locales.manual.json`: all of Sanskrit, plus rasi/graha
  abbreviations in both languages.
- `en` is a real identity table, so callers never hand-roll a fallback. An unmapped name
  returns the English input unchanged — deliberate, and normal.
- `constants/jyotish.js` now *derives* `RASI_NAMES`/`RASI_ABBR`/`PLANET_ABBR` from the
  generated tables, so English can't drift from the translations. Its ~45 existing call
  sites were left untouched.
- **Some labels sidestep this layer entirely, and that's a feature.** Since §38 (2026-07-17)
  the charts label a house with the **rasi number** and/or its **glyph** (`RASI_GLYPHS`,
  also in `constants/jyotish.js`) — both language-neutral, so they need no table, no
  translation and no review. That matters most for the **abbreviations**, which are the
  weakest part of the manual layer: a two-letter "Ar"/"Ta" is an English convention, and
  the hi/sa equivalents in `name-locales.manual.json` are inventions rather than anything a
  reader would recognise. `number_glyph` is the chart default partly for this reason. The
  abbreviation mode still exists and still goes through `localizeName`; it is simply no
  longer the only way to label a sign.
- Tests: `frontend/src/i18n/localizeName.test.js` (22). **First frontend tests in the
  repo** — run with `npx react-scripts test` (there is no `npm test` convention here yet).

Wrapped so far: `NorthIndianChart`, `SouthIndianChart`, `BirthChartPage`.

### 3.2 The B layer — `backend/astrology/engine.py`

- `to_engine_language(lang)`: `en/ta/te/hi/ka/ml` pass through, **`sa` → `hi`**, unknown
  → `en`. Handles region variants (`hi-IN`) and case.
- `lang` query param on `POST /api/astrology/yogas` and `/api/astrology/raja-yogas`;
  `frontend/src/services/api.js` sends the active `i18n.language` on those two calls.
- Tests: `backend/tests/test_engine_language.py` (12). Suite 222 → 234.

## 4. Traps — read this before touching any of it

These are the things that cost time to find. None are obvious from the code.

### 4.1 PyJHora's English is a *different naming tradition* — never join on it

`src/jhora/lang/list_values_en.txt` uses **Tamil** transliterations; our backend uses
**Sanskrit** ones. They share no strings:

| Backend (`astrology/engine.py`) | PyJHora `list_values_en.txt` |
|---|---|
| Krittika | Karthigai |
| Ardra | Thiruvaathirai |
| Pushya | Poosam |

Also `MONTH_LIST` is `Chithirai, Vaikaasi, Aani…`, and `TITHI_LIST` is
`Prathamai, Thuthiyai…` against our `Pratipada, Dwitiya…`.

**The only correspondence is positional** — both lists are in canonical order, so index
*i* is the same nakshatra in either. That is why a generator owns the tables: an
off-by-one would relabel every name with **nothing looking broken**. `localizeName.test.js`
pins known pairs at the start, middle and end of each list for exactly this reason.

### 4.2 `language=` per-call is NOT `utils.set_language()` — don't conflate the costs

todo.md used to warn that Option B means global process state, set/reset, and races. That
is true **only for the chart-name tables**. The msg-driven calls are different:

```python
yoga.get_yoga_details(jd, place, divisional_chart_factor=1, language="hi")
raja_yoga.get_raja_yoga_details(..., language="hi")
```

take a per-call argument, and `get_yoga_resources()` simply opens
`yoga_msgs_<lang>.json` and returns it. **No global state, no race, no reset.** Conflating
these made B look uniformly expensive and delayed the cheap half of it by weeks.

### 4.3 ⚠️ Never pass `language` straight to `get_yoga_details` — the language moves the astrology

This is the important one, and the obvious implementation is the wrong one.

PyJHora drives yoga **detection** off the message file's **keys**:

```python
# src/jhora/horoscope/chart/yoga.py
for yoga_function, details in msgs.items():
    yoga_exists = eval(yoga_function + '_from_jd_place')(jd, place, dcf)
```

And the key sets differ between languages:

- `yoga_msgs_hi.json` **lacks** `yukthi_samanwithavagmi_yoga_154` and `_155`
- `yoga_msgs_hi.json` **adds** `dhana_yoga` and `yukthi_samanwithavagmi_yoga`

So requesting Hindi changes **which yogas are detected**. Observed on the owner's chart:
English found `yukthi_samanwithavagmi_yoga_154`, Hindi found
`yukthi_samanwithavagmi_yoga` — same count, different composition. `dhana_yoga` could fire
on another chart in Hindi only.

**The rule: detect in English ALWAYS, then translate by key**, falling back to the English
text when a key has no translation. `test_engine_language.py` pins that en/hi/sa detect an
identical key set. `raja_yoga_msgs` and `dosha_msgs` keys *do* match across languages
today; raja yoga got the same treatment anyway, because the mechanism is identical and
could drift on any upstream bump.

### 4.4 Canonical English is an identity, not a label

In the charts, `fullName` keys `flagsByPlanet` and is handed to `onSelectPlanet`. If you
localize it, planet clicks and condition flags break — and no test would catch it.

**Apply `ln()` only where text is rendered. Never to a lookup key.** This is the single
most important thing to get right in the remaining 22 files.

### 4.5 `list_values_hi.txt` has a typo we now surface

Mrigashira is spelled `म्रृगशीर्षा` (malformed `म्` + `रृ`); it should be `मृगशीर्षा`.
We render it as-is. Undecided — see §6.

### 4.6 The backend does not `--reload`

`./dev.sh restart backend` after any `.py` edit, or you are testing the old code. The API
keeps answering, just with stale handlers.

### 4.7 The zodiac glyphs are emoji unless you say otherwise

`U+2648..U+2653` (♈..♓) have **emoji presentation by default**. Rendered bare they come out
as colour badges wherever an emoji font is installed — Chromium on Linux picks Noto Color
Emoji, and the chart labels became little coloured circles. `RASI_GLYPHS` appends **U+FE0E**
(VARIATION SELECTOR-15) to demand the text form.

The selector is **invisible in the source**, so a reformat, a copy-paste through a lossy
editor, or a well-meaning "cleanup" can drop it and nothing will look wrong in the diff —
only in the browser. `config/signLabel.test.js` asserts every glyph is exactly two code
points ending in `0xfe0e`. If you add a glyph to a **translation string** (`en.json` has one
in the sign-label hint), it needs the selector too; the JSON escape `\uFE0E` works and
survives prettier.

## 5. What's left

**The A-layer rollout is DONE (2026-07-19).** All 38 files that rendered engine
names now go through `localizeName` — signs, nakshatras and graha abbreviations
follow the selected language everywhere they are displayed.

Applied site-by-site from an explicit list rather than a regex sweep, precisely
because of §4.4. Three things that came out of doing it:

- **Four page-local copies of the abbreviation tables were retired** —
  `SIGN_ABBR` in Ephemeris, `PLANET_ABBR3` and a `RASI_ABBR` array in Advanced,
  plus direct `PLANET_ABBR` imports in six more pages. Exactly the drift the
  generated tables exist to prevent; they are all gone.
- **`AskAstrologerPage` is deliberately NOT localized.** Its four `sign_name` /
  `nakshatra` sites build the chart-context payload **sent to the model**, not
  rendered text. The prompts and tool schemas are English, so localizing it would
  hand the AI Hindi names to reason over. Engine data going *to* the model stays
  canonical; only what a human reads is translated.
- **Two §4.4 identity sites confirmed and left alone**: `PlanetExplorer`'s `name`
  (keys `flagsByPlanet`, passed to `onSelectPlanet`) and `MarriageTimeline`'s
  `p.lord` (used in `significant.has()` and the tooltip title). Only their visible
  labels are wrapped.

Scope notes: `ComparePage.compareRows` is a module-level helper so `ln` is passed
in as an argument, and `MarriageTimeline.PartnerBand` gained a block body to hold
the hook. The build caught both — neither was visible from the call sites.

**Doshas are DONE (2026-07-19)** — `lang` on `get_doshas` + the endpoint, English
keeping our curated text and other languages taking PyJHora's. Worth knowing
before touching it:

- Upstream's dosha text is **variant-indexed**, not a name+description pair:
  `dosha_msgs_*.json` holds arrays where `[0]` is "no such dosha" and `[1..n]` are
  variant-specific, and the index has a bespoke derivation per dosha (Rahu's house
  for kala sarpa, Mars' for manglik…). Our `dosha.*` predicates return booleans, so
  we do **not** index those arrays ourselves — we call
  `dosha.get_dosha_details(jd, place, language=)`, which does the derivation.
- That function keys its result by the **English display name in every language**
  (the keys come from the global `utils.resource_strings`, which we never switch).
  `_DOSHA_ENGINE_KEY` pins our catalog keys to those names — needed because
  upstream says "Manglik Dosha" where we say "Manglik (Kuja) Dosha".
- Its text is `<html>`-wrapped with `<br>`; `_strip_html` unwraps it so markup
  never reaches the reader.
- **Unlike yogas, the language cannot move the astrology here** — detection is
  boolean and never reads the message file. `test_language_never_moves_the_astrology`
  pins that, and is what would catch it becoming untrue.

Still English by design, pending decisions in §6: the Kendra-Trikona raja yoga
labels, panchanga limb values, and Ashtakoot koota names.

## 6. Open decisions — for the owner

**Owner answered 1–3 on 2026-07-19** (decisions inline below; 4–6 still open):

- **(1) Keep the sa→hi stopgap.** Do not block the A-layer rollout on authoring upstream
  Sanskrit. Sanskrit continues to show Hindi wherever PyJHora does the translating.
- **(2) Ship the hand-authored Sanskrit, but say so in the UI.** It stays unreviewed, so
  the language picker flags Sanskrit as unreviewed rather than presenting a possibly-wrong
  term with the same confidence as a checked one.
- **(3) Take the engine's dosha text — but only where it buys a translation.** The owner
  chose the engine's Hindi over our curated descriptions. Implemented **language-conditional**:
  hi/sa get the engine's text (the point of the change), `en` keeps our better descriptions,
  because swapping English for weaker English would be a pure loss — English is the default
  and needs no translation. Flagged to the owner when implemented.

1. **Author Sanskrit `lang/` files upstream.** — **DEFERRED (owner, 2026-07-19).** Until this exists, every PyJHora-sourced
   string shows `sa` users **Hindi**. Needs `src/jhora/lang/{list_values,msg_strings}_sa.txt`
   + `{yoga,raja_yoga,dosha,prediction}_msgs_sa.json` and `const.available_languages`.
   Big job — ~284 yoga descriptions alone. Once it lands, `to_engine_language` drops the
   sa→hi hop and `name-locales.manual.json` could source from upstream instead of being
   hand-authored.
2. **The hand-authored Sanskrit is unreviewed.** — **SHIP + FLAG (owner, 2026-07-19).**
   Written by Claude, not a Sanskrit reader.
   It looks right (कुम्भ, धनुस्, चन्द्र, शतभिषक्) but should be checked before it's treated
   as authoritative.
3. **Doshas.** — **DECIDED (owner, 2026-07-19): take the engine text for hi/sa, keep ours
   for en.** Keys mostly line up with `dosha_msgs_*.json`, but
   `compute_strength.get_doshas` writes its own descriptions and they're better than
   upstream's. Switching gains Hindi and loses the curated text.
4. **The `म्रृगशीर्षा` typo** (§4.5): patch `src/jhora/lang/list_values_hi.txt` (it's this
   repo) or add a hi override to the manual file.
5. **Kendra-Trikona raja yogas** are built from our own f-strings, so the A layer must
   cover them.
6. **New-page UI strings are English-only**, falling back via `fallbackLng` — the standing
   pattern for every recent feature page. Steady state, or debt to burn down?

## 7. Commands

```bash
# regenerate the name tables after editing the lang file or the manual JSON
cd web/frontend && npm run gen:names

# the A layer's tests (first frontend tests in the repo)
cd web/frontend && CI=true npx react-scripts test --testPathPattern=localizeName

# the B layer's tests + everything else
cd web/backend && venv/bin/python -m pytest tests -q

# after any backend edit
cd web && ./dev.sh restart backend
```

Adding a `lang` param to a route will trip `test_routes_inventory.py` — that guard is
working; regenerate `tests/routes_snapshot.json` and keep the diff reviewable
(`json.dump(cur, f, indent=1, sort_keys=True)`, no trailing newline).
