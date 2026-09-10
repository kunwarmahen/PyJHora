/**
 * Guard: AI prose must render through `components/Markdown.js`.
 *
 * The bug this replaces: every panel imported `react-markdown` directly, which
 * speaks CommonMark only. Models answer with GitHub-flavoured markdown, so a
 * dasha timeline written as a table reached the page as raw `| Period |` pipes.
 * The wrapper adds remark-gfm once for all ~30 surfaces — a direct import
 * anywhere else silently opts that surface back out of tables, which is
 * invisible until a model happens to emit one.
 *
 * A static sweep rather than a render test on purpose: react-markdown is
 * ESM-only and CRA's jest does not transform node_modules, so importing it
 * here would fail for reasons unrelated to the invariant being checked.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");
const WRAPPER = path.join(__dirname, "Markdown.js");

const jsFiles = (dir) =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return jsFiles(p);
    return /\.jsx?$/.test(e.name) ? [p] : [];
  });

describe("markdown rendering", () => {
  test("only the shared wrapper imports react-markdown", () => {
    const offenders = jsFiles(SRC)
      .filter((f) => f !== WRAPPER)
      .filter((f) => /from\s+["']react-markdown["']/.test(fs.readFileSync(f, "utf8")))
      .map((f) => path.relative(SRC, f));

    expect(offenders).toEqual([]);
  });

  test("the wrapper enables GitHub-flavoured markdown", () => {
    const src = fs.readFileSync(WRAPPER, "utf8");
    expect(src).toMatch(/from\s+["']remark-gfm["']/);
    expect(src).toMatch(/remarkPlugins=\{\[\s*remarkGfm\s*\]\}/);
  });

  test("tables render inside a scroll container so wide ones cannot widen the page", () => {
    const src = fs.readFileSync(WRAPPER, "utf8");
    expect(src).toMatch(/md-table-wrap/);
    const css = fs.readFileSync(path.join(SRC, "styles", "Markdown.css"), "utf8");
    expect(css).toMatch(/\.md-table-wrap\s*\{[^}]*overflow-x:\s*auto/);
  });
});
