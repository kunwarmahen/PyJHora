/**
 * Birth details carried from the landing page's anonymous preview into the
 * welcome flow after sign-up (§76.7), so nobody types them twice.
 *
 * sessionStorage, not localStorage: the details are someone's birth date, time
 * and place, entered before they had an account. They should live only as long
 * as this tab, and never be waiting on a shared computer for the next visitor.
 * Nothing is sent to the server until the welcome flow saves the profile.
 */
const KEY = "jyotir_preview_birth";

const FIELDS = ["dob", "tob", "place", "latitude", "longitude", "timezone", "time_accuracy"];

/** Keep only the fields we use, and only if the essentials are present. */
export const sanitizeHandoff = (bd) => {
  if (!bd || typeof bd !== "object") return null;
  const out = {};
  FIELDS.forEach((k) => {
    if (bd[k] !== undefined && bd[k] !== null && bd[k] !== "") out[k] = bd[k];
  });
  const ok =
    /^\d{4}-\d{2}-\d{2}$/.test(out.dob || "") &&
    /^\d{1,2}:\d{2}(:\d{2})?$/.test(out.tob || "") &&
    Number.isFinite(Number(out.latitude)) &&
    Number.isFinite(Number(out.longitude)) &&
    Number.isFinite(Number(out.timezone));
  return ok ? out : null;
};

export const saveHandoff = (bd) => {
  const clean = sanitizeHandoff(bd);
  if (!clean) return;
  try {
    sessionStorage.setItem(KEY, JSON.stringify(clean));
  } catch {
    // private mode / quota — the welcome flow just starts empty
  }
};

export const loadHandoff = () => {
  try {
    return sanitizeHandoff(JSON.parse(sessionStorage.getItem(KEY) || "null"));
  } catch {
    return null;
  }
};

export const clearHandoff = () => {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // ignore
  }
};
