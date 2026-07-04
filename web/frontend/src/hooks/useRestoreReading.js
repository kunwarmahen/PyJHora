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
  const doneRef = useRef(null);
  const cbRef = useRef(onRestore);
  cbRef.current = onRestore;

  useEffect(() => {
    // Clearing the param (below) drops readingId to null — reset the guard so
    // clicking the *same* item again later re-restores it.
    if (!readingId) {
      doneRef.current = null;
      return;
    }
    if (doneRef.current === readingId) return;
    doneRef.current = readingId;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await astrologyService.getConversation(readingId);
        if (cancelled || !data) return;
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
        // at the top and it looks like nothing happened. Poll briefly for it.
        if (!cancelled) revealReading();
      } catch (e) {
        /* reading may have been deleted — ignore */
      } finally {
        // Drop the query param so a page refresh / manual regenerate isn't stuck
        // re-restoring the same snapshot.
        if (!cancelled) {
          const next = new URLSearchParams(params);
          next.delete("reading");
          setParams(next, { replace: true });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readingId]);
}

// Scroll the restored reading into view once it renders (the page may still be
// loading its factual data, so retry for a few seconds before giving up).
function revealReading(tries = 0) {
  const el = document.querySelector(
    ".ai-panel__reading, .sbc-ai-markdown, .transit-chat__messages"
  );
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  if (tries < 24) setTimeout(() => revealReading(tries + 1), 150);
}
