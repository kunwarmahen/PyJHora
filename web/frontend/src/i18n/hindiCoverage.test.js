/**
 * Hindi covers every UI string (todo.md §85.2, owner decision 2026-10-06:
 * "translate, Hindi first"). A key added to en.json without its hi.json twin
 * would silently fall back to English for a Hindi reader — this is what stops it.
 */
import en from "./locales/en.json";
import hi from "./locales/hi.json";

const flat = (obj, prefix = "") =>
  Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? flat(v, `${prefix}${k}.`) : [[`${prefix}${k}`, v]]
  );

// Strings that are correctly identical in both languages.
const SAME_IN_BOTH = new Set([
  "profile.notifyEmailPlaceholder",
  "settings.tabs.ai",
  "settings.account.emailPlaceholder",
  "auth.forgot.identifierPlaceholder",
  "journal.noDasha",
  "bhrigu.emptySign",
  "gochara.noVedha",
]);

const hiFlat = Object.fromEntries(flat(hi));
const placeholders = (s) => (String(s).match(/\{\{\s*\w+\s*\}\}/g) || []).sort();

describe("Hindi coverage", () => {
  test("every en key has a Hindi string", () => {
    const missing = flat(en)
      .filter(([k]) => !(k in hiFlat))
      .map(([k]) => k);
    expect(missing).toEqual([]);
  });

  test("no Hindi string is the English copied over", () => {
    const copied = flat(en)
      .filter(([k, v]) => hiFlat[k] === v && /[A-Za-z]/.test(v) && !SAME_IN_BOTH.has(k))
      .map(([k]) => k);
    expect(copied).toEqual([]);
  });

  test("Hindi keeps every interpolation placeholder", () => {
    const broken = flat(en)
      .filter(([k, v]) => k in hiFlat)
      .filter(([k, v]) => placeholders(v).join() !== placeholders(hiFlat[k]).join())
      .map(([k]) => k);
    expect(broken).toEqual([]);
  });
});
