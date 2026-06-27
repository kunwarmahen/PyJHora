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
