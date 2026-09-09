/**
 * Reading a sign out of a chart-position payload.
 *
 * The backend publishes two sign-ish numbers and they are not interchangeable
 * (`web/todo.md` §65):
 *
 *   sign_num   1-based sign — the CELL a Kundali draws the graha in
 *   house      the BHAVA, counted whole-sign from that chart's own lagna
 *
 * Only `sign_num` places a graha on the diagram. `house` must never be used for
 * it: for a lagna `house` is always 1, so falling back to it silently numbers
 * every cell with its own house number — which is precisely what a stale build
 * did to every chart in the app after the rename (§66). A number that is wrong
 * but plausible is worse than no number, so this returns null and the caller
 * shows nothing rather than guessing.
 *
 * `rasi` (0-based) is the only safe legacy fallback: it is unambiguous, and
 * payloads that predate the rename still carry it.
 *
 * Kept in config/ so it is directly unit-testable — same reasoning as
 * signLabel.js.
 */
export const signNumOf = (pos) => {
  if (!pos) return null;
  if (Number.isInteger(pos.sign_num) && pos.sign_num >= 1 && pos.sign_num <= 12) {
    return pos.sign_num;
  }
  if (Number.isInteger(pos.rasi) && pos.rasi >= 0 && pos.rasi <= 11) {
    return pos.rasi + 1;
  }
  return null;
};

/** The sign in a visual house position, counting from the lagna's cell. */
export const signAtVisualHouse = (lagnaSignNum, visualHouseNum) =>
  lagnaSignNum == null ? null : ((lagnaSignNum - 1 + (visualHouseNum - 1)) % 12) + 1;
