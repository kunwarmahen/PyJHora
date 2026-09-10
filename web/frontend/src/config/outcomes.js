// The "did this land?" vocabulary (§68.7), mirroring outcomes.py's VERDICTS.
//
// It lives in config/ rather than inside the control because three separate
// things render it — the chip, the editor's buttons and the track-record tally —
// and because a registry importable without pulling in the API client is the
// only kind the test suite can sweep.
//
// Order is best → worst for display. `not_yet` sits among them deliberately: it
// is the honest state of most predictions most of the time, and offering only
// hit/miss forces a judgement the reader cannot yet make. The backend keeps it
// out of the hit rate and out of what the model is shown.
export const VERDICTS = ["happened", "partly", "not_yet", "didnt"];

// Everything except "too early to tell" — the verdicts that count.
export const SETTLED = VERDICTS.filter((v) => v !== "not_yet");
