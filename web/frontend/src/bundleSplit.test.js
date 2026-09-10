/**
 * Guards the route-level code splitting (§68.4).
 *
 * The initial bundle grew to 406 KB gzipped one honest static import at a time,
 * and nothing in the repo noticed. These are source-level assertions rather
 * than a build measurement so they run in the normal suite: adding
 * `import { NewPage } from "./pages/NewPage"` to App.js, or pulling a heavy
 * library into a module that loads eagerly, fails here instead of quietly
 * costing every visitor the download.
 *
 * The size assertion at the end only runs when a production build happens to be
 * on disk — it is a backstop, not the guard.
 */
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

const SRC = __dirname;
const read = (p) => fs.readFileSync(path.join(SRC, p), "utf8");

const allSourceFiles = () => {
  const out = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name.endsWith(".js")) out.push(full);
    }
  };
  walk(SRC);
  return out;
};

// Static `import ... from "<module>"` only — a dynamic import() is the point.
const staticImporters = (specifier) =>
  allSourceFiles()
    .filter((f) => !f.endsWith(".test.js"))
    .filter((f) => {
      const src = fs.readFileSync(f, "utf8");
      const re = new RegExp(`^\\s*import\\s[^;]*?["']${specifier}(/[^"']*)?["']`, "m");
      return re.test(src);
    })
    .map((f) => path.relative(SRC, f));

describe("App routes are code-split", () => {
  const app = read("App.js");

  it("imports no page statically", () => {
    expect(app).not.toMatch(/^\s*import\s.*["']\.\/pages\//m);
  });

  it("routes every page through the lazy helper", () => {
    const declared = [...app.matchAll(/const (\w+) = page\(/g)].map((m) => m[1]);
    const rendered = new Set([...app.matchAll(/<(\w+Page)[\s/>]/g)].map((m) => m[1]));
    expect(declared.length).toBeGreaterThan(40);
    for (const name of rendered) expect(declared).toContain(name);
  });

  it("holds every lazy route behind one Suspense boundary with a fallback", () => {
    expect(app).toMatch(/<Suspense fallback=\{<LoadingState \/>\}>/);
    expect(app).toMatch(/<RouteErrorBoundary>/);
  });
});

describe("heavy libraries stay out of the eager graph", () => {
  // Leaflet serves one collapsed dialog; it belongs to the lazy MapCanvas only.
  it("keeps leaflet inside MapCanvas", () => {
    expect(staticImporters("leaflet").sort()).toEqual(["components/MapCanvas.js"]);
    expect(staticImporters("react-leaflet").sort()).toEqual(["components/MapCanvas.js"]);
  });

  // Markdown is used by ~29 pages, all of them lazy, so webpack can put the
  // parser in a shared async chunk — as long as this one wrapper is its only
  // static importer.
  it("keeps the markdown stack inside the Markdown component", () => {
    expect(staticImporters("react-markdown").sort()).toEqual(["components/Markdown.js"]);
    expect(staticImporters("remark-gfm").sort()).toEqual(["components/Markdown.js"]);
  });

  // PDF export was already deferred before §68.4; keep it that way.
  it("keeps jspdf and html2canvas dynamic", () => {
    expect(staticImporters("jspdf")).toEqual([]);
    expect(staticImporters("html2canvas")).toEqual([]);
  });

  // Only English ships with the app; hi/sa are fetched when selected.
  it("bundles only the English locale", () => {
    const importers = allSourceFiles()
      .filter((f) => !f.endsWith(".test.js"))
      .filter((f) =>
        /^\s*import\s[^;]*?["'][^"']*locales\/(hi|sa)\.json["']/m.test(fs.readFileSync(f, "utf8"))
      )
      .map((f) => path.relative(SRC, f));
    expect(importers).toEqual([]);
    expect(read("i18n/index.js")).toMatch(/import\("\.\/locales\/hi\.json"\)/);
  });
});

describe("built main chunk", () => {
  // A budget with headroom, in gzipped bytes: 158 KB at the time of writing,
  // against 443 KB before the split. Crossing this means something large became
  // eager again — find it before shipping rather than after.
  const BUDGET_GZIP = 200 * 1024;
  const buildJs = path.join(SRC, "..", "build", "static", "js");

  it("stays inside its gzip budget", () => {
    if (!fs.existsSync(buildJs)) return; // no production build on disk; nothing to check
    const main = fs.readdirSync(buildJs).find((f) => /^main\..*\.js$/.test(f));
    if (!main) return;
    const gz = zlib.gzipSync(fs.readFileSync(path.join(buildJs, main))).length;
    expect(gz).toBeLessThan(BUDGET_GZIP);
  });
});
