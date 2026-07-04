import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { astrologyService } from "../services/api";

// Reopen a saved AI reading on its own tool page. When the URL carries
// `?reading=<id>` (the unified History page deep-links here), this fetches the
// stored item and hands the caller its `context` (the inputs used) plus the exact
// saved AI text — so the page can restore its controls and show the snapshot
// verbatim, without re-generating anything.
//
// `onRestore({ context, reading, model, birthDetails, source, data })` is invoked
// once per reading id. Pages typically: set their input state from `context`,
// then stash `{ reading, model }` and apply it to their AI panel once their
// factual load settles (see the pending-reading pattern in the tool pages).
export function useRestoreReading(onRestore) {
  const [params, setParams] = useSearchParams();
  const readingId = params.get("reading");
  // Which id we've already restored, so we don't re-run for it. NOTE: we
  // deliberately do NOT abort the async on effect-cleanup — React 18 StrictMode
  // double-invokes effects (setup → cleanup → setup) in dev, and aborting the
  // first run while the guard skips the second means onRestore would never fire.
  // Letting the async complete is safe (setState on an unmounted component is a
  // no-op in React 18).
  const handledRef = useRef(null);
  const cbRef = useRef(onRestore);
  cbRef.current = onRestore;
  // Latest search params for the clear-the-param step (avoids a stale closure).
  const paramsRef = useRef(params);
  paramsRef.current = params;

  useEffect(() => {
    // Clearing the param (below) drops readingId to null — reset the guard so
    // clicking the *same* item again later re-restores it.
    if (!readingId) {
      handledRef.current = null;
      return;
    }
    if (handledRef.current === readingId) return;
    handledRef.current = readingId;
    (async () => {
      try {
        const { data } = await astrologyService.getConversation(readingId);
        if (!data) return;
        const msgs = data.messages || [];
        const lastAi = [...msgs].reverse().find((m) => m.role === "assistant");
        cbRef.current({
          context: data.context || {},
          reading: lastAi?.content || "",
          model: lastAi?.model || lastAi?.provider || "",
          birthDetails: data.birth_details || null,
          source: data.source,
          data,
        });
        // The reading renders lower on a long page (and only once the page's
        // factual data loads), so bring it into view — otherwise the user lands
        // at the top and it looks like nothing happened.
        revealReading();
      } catch (e) {
        /* reading may have been deleted — ignore */
      } finally {
        // Drop the query param so a refresh / manual regenerate isn't stuck
        // re-restoring the same snapshot.
        const next = new URLSearchParams(paramsRef.current);
        next.delete("reading");
        setParams(next, { replace: true });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readingId]);
}

// Scroll the restored reading into view once it renders. The page may still be
// loading its factual data (some pages — e.g. Vedic Clock's retrograde epicycle —
// take a few seconds and only mount the reading card afterwards), so watch the DOM
// with a MutationObserver rather than a short poll, and give up after 15s.
const READING_SELECTOR =
  ".ai-panel__reading, .sbc-ai-markdown, .transit-chat__messages";

function revealReading() {
  const scroll = (el) => el.scrollIntoView({ behavior: "smooth", block: "center" });
  const now = document.querySelector(READING_SELECTOR);
  if (now) {
    scroll(now);
    return;
  }
  if (typeof MutationObserver === "undefined") return;
  const obs = new MutationObserver(() => {
    const el = document.querySelector(READING_SELECTOR);
    if (el) {
      obs.disconnect();
      scroll(el);
    }
  });
  obs.observe(document.body, { childList: true, subtree: true });
  setTimeout(() => obs.disconnect(), 15000);
}
