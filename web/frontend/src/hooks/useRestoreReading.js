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
    if (!readingId || doneRef.current === readingId) return;
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
