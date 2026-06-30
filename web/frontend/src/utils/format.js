// Safe display helpers for birth-detail fields.
// These never throw on missing/short data — they fall back to an em dash.

const DASH = "—";

/**
 * Show just the calendar date from a `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM` string.
 * Returns "—" for anything missing or non-string (avoids `.split` crashes).
 */
export const formatDate = (dob) => {
  if (!dob || typeof dob !== "string") return DASH;
  return dob.split("T")[0] || DASH;
};

/** Show a value, or a dash placeholder when it's empty/missing. */
export const orDash = (v) => (v === null || v === undefined || v === "" ? DASH : v);

/**
 * Coerce an Axios error into a plain string for display.
 *
 * FastAPI's 422 responses put `detail` as an *array* of validation objects
 * ({type, loc, msg, input, url}); handing that straight to React throws
 * "Objects are not valid as a React child". This flattens any shape — string,
 * array of validation objects, or a single object — into a readable message,
 * falling back to `fallback` when nothing usable is present.
 */
export const errorMessage = (err, fallback = "Something went wrong") => {
  const detail = err?.response?.data?.detail ?? err?.response?.data?.error;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => (typeof d === "string" ? d : d?.msg)).filter(Boolean);
    if (msgs.length) return msgs.join("; ");
  } else if (detail && typeof detail === "object") {
    if (typeof detail.msg === "string") return detail.msg;
  }
  if (typeof err?.message === "string" && err.message) return err.message;
  return fallback;
};

/**
 * Map an i18next language code to a BCP-47 locale for Intl/`toLocaleDateString`.
 * Sanskrit has no widely-supported Intl locale, so it falls back to en-IN
 * (Indian date order, English month names) rather than throwing.
 */
export const intlLocale = (lang) => {
  const base = (lang || "en").split("-")[0];
  return { en: "en-US", hi: "hi-IN", sa: "en-IN" }[base] || "en-US";
};
