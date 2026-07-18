/**
 * Tab resolution — which tabs a page shows, and which one is open (§15).
 *
 * Kept as pure functions (like `uiMode.js` and `features.js`) so the rules that
 * can actually strand a user are directly unit-testable, while the component and
 * the router/settings plumbing stay thin around them.
 *
 * Two rules carry the weight:
 *
 *  1. A tab marked `advanced` is hidden in Essentials mode — that's what makes
 *     the page genuinely simpler rather than merely gated.
 *  2. ...unless the URL explicitly asks for it. Deep-links must never dead-end:
 *     AI readings, digests and saved history all link into pages, and once
 *     content lives behind a tab a link to it has to open it — otherwise the
 *     link silently lands on the wrong content. This mirrors `AdvancedNotice`,
 *     which shows an advanced *page* in Essentials mode rather than redirecting
 *     away from it.
 */

export const TAB_PARAM = "tab";

/**
 * The tabs to render.
 *
 * `tabs` is [{ key, label, advanced? }]. `requestedKey` is whatever the URL
 * asked for (or null) — an advanced tab named there is revealed, per rule 2.
 */
export const visibleTabs = (tabs, uiMode, requestedKey = null) => {
  const list = Array.isArray(tabs) ? tabs : [];
  if (uiMode === "advanced") return list;
  return list.filter((t) => !t.advanced || t.key === requestedKey);
};

/**
 * The tab that should be open.
 *
 * Falls back to the first visible tab when the URL names nothing, names a tab
 * that doesn't exist, or names one hidden in this mode — a stale or hand-edited
 * link lands somewhere sensible instead of on a blank page.
 */
export const resolveActiveTab = (tabs, uiMode, requestedKey = null) => {
  const visible = visibleTabs(tabs, uiMode, requestedKey);
  if (!visible.length) return null;
  const match = visible.find((t) => t.key === requestedKey);
  return match ? match.key : visible[0].key;
};

/**
 * Whether selecting `nextKey` should push a new URL.
 *
 * Only ever consulted when the user actually picks a tab — the initial resolve
 * deliberately does not write, so landing on a page with no `?tab=` costs no
 * history entry and Back still leaves the page rather than undoing a default the
 * user never chose. Re-clicking the open tab is likewise not a navigation.
 */
export const shouldWriteTab = (requestedKey, nextKey) =>
  Boolean(nextKey) && requestedKey !== nextKey;
