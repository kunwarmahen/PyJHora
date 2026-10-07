/**
 * The landing page's copy lives in the locale files (§83.6).
 *
 * The page harness mounts LandingPage, but a mistyped key renders as the raw
 * "landing.x.y" string rather than failing, so pin the keys themselves: every
 * literal key the page asks for exists in en, every key it builds from its
 * PLANS/FEATURES ids exists, and hi carries the same shape as en.
 */
import fs from "fs";
import path from "path";
import en from "../i18n/locales/en.json";
import hi from "../i18n/locales/hi.json";

const SRC = fs.readFileSync(path.join(__dirname, "LandingPage.js"), "utf8");

const get = (obj, dotted) =>
  dotted.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);

const shape = (v) => {
  if (Array.isArray(v)) return v.map(shape);
  if (v && typeof v === "object")
    return Object.fromEntries(Object.keys(v).map((k) => [k, shape(v[k])]));
  return "s";
};

test("every literal landing key the page uses exists in en", () => {
  const keys = [...SRC.matchAll(/(?:t\(|i18nKey=|list\()"(landing\.[\w.]+)"/g)].map((m) => m[1]);
  expect(keys.length).toBeGreaterThan(40);
  const missing = keys.filter((k) => get(en, k) === undefined);
  expect(missing).toEqual([]);
});

test("keys built from PLANS and FEATURES ids exist", () => {
  const ids = (block) => [...block.matchAll(/(?:id|key): "(\w+)"/g)].map((m) => m[1]);
  const plans = ids(SRC.slice(SRC.indexOf("const PLANS"), SRC.indexOf("const FEATURES")));
  const feats = ids(
    SRC.slice(SRC.indexOf("const FEATURES"), SRC.indexOf("function makeStarfield"))
  );
  expect(plans).toEqual(["free", "pro", "practitioner"]);
  expect(feats).toHaveLength(6);
  plans.forEach((id) => {
    ["name", "desc", "features", "cta"].forEach((f) =>
      expect(get(en, `landing.pricing.plans.${id}.${f}`)).toBeDefined()
    );
  });
  feats.forEach((id) => {
    ["title", "body", "tag"].forEach((f) =>
      expect(get(en, `landing.features.items.${id}.${f}`)).toBeDefined()
    );
  });
});

test("hi mirrors en's landing shape", () => {
  expect(shape(hi.landing)).toEqual(shape(en.landing));
});
