import { useEffect, useState } from "react";
import { aiActivityService } from "../services/api";

// One shared view of what the AI is working on for this user (the server's
// /api/ai/activity — backend/ai_activity.py). Every page's header shows it and
// History lists it, so the store is a module singleton: however many components
// subscribe, there is one poll.
//
// Polling is quick (5 s) only while something is running, and slow (60 s)
// otherwise — a job started elsewhere (another tab, another device) still shows
// up within the minute. A job started here announces itself at once through the
// `jyotir:ai-activity` event (services/api.js), and coming back to the tab
// refreshes straight away.

const FAST_MS = 5000;
const SLOW_MS = 60000;
const EMPTY = { items: [], running: 0, ready: 0, loaded: false };

let state = EMPTY;
const subscribers = new Set();
let timer = null;
let inflight = null;

const emit = () => subscribers.forEach((fn) => fn(state));

const recount = (items) => ({
  items,
  running: items.filter((i) => i.status === "running").length,
  ready: items.filter((i) => i.status !== "running").length,
  loaded: true,
});

const schedule = () => {
  clearTimeout(timer);
  if (!subscribers.size) return;
  timer = setTimeout(
    () => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") schedule();
      else refreshAiActivity();
    },
    state.running > 0 ? FAST_MS : SLOW_MS
  );
};

export const refreshAiActivity = () => {
  let signedIn = false;
  try {
    signedIn = !!localStorage.getItem("access_token");
  } catch (e) {
    /* storage blocked */
  }
  if (!signedIn) return Promise.resolve();
  if (inflight) return inflight;
  inflight = aiActivityService
    .list()
    .then((r) => {
      state = recount(r.data?.items || []);
      emit();
    })
    .catch(() => {
      /* offline or signed out: keep what we had, try again later */
    })
    .finally(() => {
      inflight = null;
      schedule();
    });
  return inflight;
};

/** Drop an item from the list now and tell the server it has been seen. */
export const markAiActivitySeen = (jobId) => {
  state = recount(state.items.filter((i) => i.id !== jobId));
  emit();
  return aiActivityService.markSeen(jobId).catch(() => {});
};

const onNudge = () => refreshAiActivity();
const onVisible = () => {
  if (document.visibilityState === "visible") refreshAiActivity();
};

export function useAiActivity() {
  const [snapshot, setSnapshot] = useState(state);
  useEffect(() => {
    subscribers.add(setSnapshot);
    if (subscribers.size === 1) {
      window.addEventListener("jyotir:ai-activity", onNudge);
      document.addEventListener("visibilitychange", onVisible);
    }
    refreshAiActivity();
    return () => {
      subscribers.delete(setSnapshot);
      if (!subscribers.size) {
        window.removeEventListener("jyotir:ai-activity", onNudge);
        document.removeEventListener("visibilitychange", onVisible);
        clearTimeout(timer);
      }
    };
  }, []);
  return snapshot;
}

// For tests.
export const __testing = {
  reset: () => {
    state = EMPTY;
    clearTimeout(timer);
    inflight = null;
  },
  recount,
};
