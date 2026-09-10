import en from "../i18n/locales/en.json";
import { VERDICTS, SETTLED } from "../config/outcomes";

// §68.7. The verdict list is shared by the chips, the editor and the track-record
// tally, and each one renders `outcome.verdict.<v>`. A fifth verdict added to the
// backend and mirrored here without its string would render the raw key in three
// places at once — this is the class-level guard for that, not a spot-check.
describe("did-this-land verdicts", () => {
  it("every verdict has a label", () => {
    const missing = VERDICTS.filter((v) => !en.outcome.verdict[v]);
    expect(missing).toEqual([]);
  });

  it("no orphaned verdict labels", () => {
    expect(Object.keys(en.outcome.verdict).sort()).toEqual([...VERDICTS].sort());
  });

  it("keeps 'too early to tell' in the vocabulary, and out of the rate", () => {
    // Offering only hit/miss forces a judgement most readers can't yet make —
    // and the backend excludes this one from the hit rate on purpose, so the
    // frontend's idea of "settled" has to agree with outcomes.py's SETTLED.
    expect(VERDICTS).toContain("not_yet");
    expect(SETTLED).toEqual(VERDICTS.filter((v) => v !== "not_yet"));
  });
});
