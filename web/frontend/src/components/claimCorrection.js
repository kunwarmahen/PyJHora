/**
 * The claim checker's correction block (backend `claim_check.annotation`) lifted
 * out of an answer so it can be shown ABOVE the prose instead of under it.
 *
 * Streaming answers cannot be regenerated, so a reading that contradicts its own
 * chart keeps its wrong sentences and gets a "does not match" note appended. At
 * the foot of a long career reading nobody saw it: the owner read "Sun in the
 * 10th" for a Sun in the 11th and found the correction only after arguing with
 * the model. Parsing the saved text (rather than the live `claim_check` event)
 * means a reopened conversation, a saved reading and the live stream all get the
 * same callout.
 *
 * Must stay in step with `CORRECTION_HEADER` in backend/claim_check.py.
 */
export const CORRECTION_HEADER = "⚠ Checked against the computed chart";

// The annotation opens with a horizontal rule, then the bold header.
const BLOCK = /\n+-{3,}\s*\n+(?=\*\*⚠ Checked against the computed chart)/;

export const splitCorrection = (text) => {
  if (typeof text !== "string" || !text.includes(CORRECTION_HEADER)) {
    return { body: text, correction: null };
  }
  const m = BLOCK.exec(text);
  if (!m) return { body: text, correction: null };
  return {
    body: text.slice(0, m.index),
    correction: text.slice(m.index + m[0].length).trim(),
  };
};
