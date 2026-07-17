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

function cssFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return cssFiles(p);
    return e.name.endsWith(".css") ? [p] : [];
  });
}

/** Strip comments — prose may legitimately mention a hex. */
const decolour = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "");

describe("theme tokens", () => {
  it("defines every token the stylesheets reference", () => {
    const all = cssFiles(SRC).map((f) => fs.readFileSync(f, "utf8")).join("\n");
    const defined = new Set(
      [...all.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)].map((m) => m[1]),
    );
    // Set from JS at runtime rather than in any stylesheet.
    const runtime = new Set(["--lvl-accent", "--avatar"]);
    const used = new Set(
      [...decolour(all).matchAll(/var\(\s*(--[a-z0-9-]+)/g)].map((m) => m[1]),
    );
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

  it("confines App.css literals to the :root token block", () => {
    const src = decolour(fs.readFileSync(APP_CSS, "utf8"));
    const root = src.match(/:root\s*\{[\s\S]*?\n\}/);
    expect(root).not.toBeNull();
    const rest = src.replace(root[0], "");
    expect(rest.match(LITERAL)).toBeNull();
  });
});
