/**
 * §37 guard: the theme tokens are the only place a colour may be spelled out.
 *
 * A colour literal in a stylesheet is a value dark mode cannot reach — it
 * stays light-on-light no matter what `data-theme` says. This test fails on
 * any literal outside App.css's :root so that whole class of bug can't
 * re-enter the app one hex at a time.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");
const APP_CSS = path.join(SRC, "App.css");
const LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\(\s*[0-9]/g;

/**
 * Named colours count too. This is not hypothetical: `background: white`
 * appeared 66 times and sailed straight through the hex/rgba audit, leaving
 * white cards sitting in the middle of the dark theme.
 */
// The (?<![-\w]) / (?![-\w]) guards matter: \b alone treats the hyphen in
// var(--white-rgb) and --sacred-white as a boundary and flags the tokens
// themselves.
const KEYWORD = new RegExp(
  String.raw`^\s*(?:background|background-color|color|fill|stroke|border[a-z-]*)\s*:` +
    String.raw`[^;]*(?<![-\w])(?:white|black|silver|gray|grey|ivory|snow|whitesmoke|red|lime|aqua|fuchsia)(?![-\w])`,
  "gm"
);

/** Drop @media print blocks: those deliberately force a white sheet (§37). */
const dropPrint = (s) => s.replace(/@media\s+print\s*\{(?:[^{}]|\{[^{}]*\})*\}/g, "");

function cssFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return cssFiles(p);
    return e.name.endsWith(".css") ? [p] : [];
  });
}

/** Strip comments — prose may legitimately mention a hex. */
const decolour = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "");

describe("inline SVG paint", () => {
  // fill="white" is an SVG presentation attribute, not CSS — it sailed through
  // the stylesheet audit and left the kundali a white slab in dark mode.
  const PAINT = /\b(?:fill|stroke)=["'](?:white|black|#[0-9a-fA-F]{3,8}|rgba?\(\s*[0-9])/g;

  const jsFiles = (dir) =>
    fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) return jsFiles(p);
      return /\.jsx?$/.test(e.name) && !/\.test\./.test(e.name) ? [p] : [];
    });

  it("paints SVG from tokens, not literals", () => {
    const offenders = [];
    for (const file of jsFiles(SRC)) {
      const hits = fs.readFileSync(file, "utf8").match(PAINT);
      if (hits) offenders.push(`${path.relative(SRC, file)}: ${hits.join(", ")}`);
    }
    expect(offenders).toEqual([]);
  });

  it("styles inline JS from tokens, not literals", () => {
    // style={{ background: "#fff7ed" }} is invisible to a stylesheet audit —
    // this is what left the Sarvatobhadra chakra a light slab on a dark page.
    const INLINE =
      /(?:background|backgroundColor|color|borderColor|border|fill|stroke)\s*:\s*"[^"]*(?:#[0-9a-fA-F]{3,8}|rgba?\(\s*[0-9]|(?<![-\w])(?:white|black)(?![-\w]))[^"]*"/g;
    const offenders = [];
    for (const file of jsFiles(SRC)) {
      // exportChart deliberately pins the canvas to #ffffff — see §37.
      if (file.endsWith("exportChart.js")) continue;
      const hits = fs.readFileSync(file, "utf8").match(INLINE);
      if (hits) offenders.push(`${path.relative(SRC, file)}: ${hits.join(", ")}`);
    }
    expect(offenders).toEqual([]);
  });
});

describe("theme tokens", () => {
  it("defines every token the stylesheets reference", () => {
    const all = cssFiles(SRC)
      .map((f) => fs.readFileSync(f, "utf8"))
      .join("\n");
    const defined = new Set([...all.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)].map((m) => m[1]));
    // Set from JS at runtime rather than in any stylesheet.
    const runtime = new Set(["--lvl-accent", "--avatar"]);
    const used = new Set([...decolour(all).matchAll(/var\(\s*(--[a-z0-9-]+)/g)].map((m) => m[1]));
    const missing = [...used].filter((t) => !defined.has(t) && !runtime.has(t));
    expect(missing).toEqual([]);
  });

  it("keeps colour literals out of every stylesheet but the token layer", () => {
    const offenders = [];
    for (const file of cssFiles(SRC)) {
      if (file === APP_CSS) continue;
      const hits = decolour(fs.readFileSync(file, "utf8")).match(LITERAL);
      if (hits) offenders.push(`${path.relative(SRC, file)}: ${hits.join(", ")}`);
    }
    expect(offenders).toEqual([]);
  });

  it("keeps NAMED colours out too — `background: white` is still a literal", () => {
    const offenders = [];
    for (const file of cssFiles(SRC)) {
      const src = dropPrint(decolour(fs.readFileSync(file, "utf8")));
      const hits = src.match(KEYWORD);
      if (hits) {
        offenders.push(`${path.relative(SRC, file)}: ${hits.map((h) => h.trim()).join(" | ")}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("confines App.css literals to the token blocks", () => {
    // The light :root and the themed overrides are the only place a colour may
    // be spelled out. Everything else in App.css must go through a token.
    const src = decolour(fs.readFileSync(APP_CSS, "utf8"));
    const light = src.match(/^:root\s*\{[\s\S]*?\n\}/m);
    const dark = src.match(/:root\[data-theme="dark"\]\s*\{[\s\S]*?\n {2}\}/);
    expect(light).not.toBeNull();
    expect(dark).not.toBeNull();
    const rest = src.replace(light[0], "").replace(dark[0], "");
    expect(rest.match(LITERAL)).toBeNull();
  });

  it("keeps the dark theme out of print, so reports stay light", () => {
    // Pinned because it is load-bearing and invisible: the dark block is
    // wrapped in @media screen precisely so print falls back to the light
    // :root. Unwrap it and every PDF silently turns into dark-on-dark.
    // decolour() first: the comment above the block says "@media screen" too,
    // and matching that would pass on the documentation instead of the rule.
    const src = decolour(fs.readFileSync(APP_CSS, "utf8"));
    const i = src.indexOf(':root[data-theme="dark"]');
    const screen = src.lastIndexOf("@media screen", i);
    expect(screen).toBeGreaterThan(-1);
    // ...and nothing closes the at-rule between it and the dark block.
    expect(src.slice(screen, i)).not.toContain("}");
  });

  it("gives the dark theme a value for every themed token", () => {
    // A token the light theme defines but dark forgets keeps its LIGHT value —
    // e.g. a cream surface surviving into dark mode as a bright slab.
    const src = fs.readFileSync(APP_CSS, "utf8");
    const decls = (re) => {
      const m = src.match(re);
      return new Map(
        [...m[0].matchAll(/^\s*(--[a-z0-9-]+)\s*:([^;]*);/gm)].map((x) => [x[1], x[2]])
      );
    };
    const light = decls(/^:root\s*\{[\s\S]*?\n\}/m);
    const dark = decls(/:root\[data-theme="dark"\]\s*\{[\s\S]*?\n {2}\}/);
    // Tokens that are intentionally theme-independent: brand hues, geometry
    // and type. Anything else missing from dark is a bug.
    const shared = (t) =>
      /^--(font|space|radius|saffron|marigold|vermillion|emerald|cosmic|terracotta|temple|night|white-rgb|black-rgb|card-bg|border-color|cream|text$|ink-light|accent$|gold$|planet)/.test(
        t
      ) || ["--surface-page", "--surface-inverse", "--text", "--radius-pill"].includes(t);
    // A pure alias (`--x: var(--y)`) resolves through to its target at use time,
    // so it inherits whatever dark gives --y and needs no override of its own —
    // restating it in the dark block would be the bug, freezing the alias to one
    // value. This is by VALUE, not by name: an alias earns the exemption by
    // actually being one, so a literal that later replaces it is caught again.
    const alias = (t) => /^\s*var\(--[a-z0-9-]+\)\s*$/.test(light.get(t));
    const missing = [...light.keys()].filter((t) => !dark.has(t) && !shared(t) && !alias(t));
    expect(missing).toEqual([]);
  });
});
