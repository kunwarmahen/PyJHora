import { parseLocalDate, todayISO } from "./format";

// This one is invisible in India and wrong for half the world: the engine hands
// back plain calendar dates ("2026-08-05"), the Date constructor reads those as
// UTC midnight, and every timezone west of Greenwich then renders the day
// before. It shipped as "As of Aug 4" on a chart cast for Aug 5 in Cary, NC.
describe("parseLocalDate", () => {
  const fmt = (d) =>
    d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });

  it("keeps a date-only string on its own calendar day", () => {
    const d = parseLocalDate("2026-08-05");
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(7); // August
    expect(d.getDate()).toBe(5);
    expect(fmt(d)).toBe("Aug 5, 2026");
  });

  it("does not drift across a month or year boundary", () => {
    expect(fmt(parseLocalDate("2026-01-01"))).toBe("Jan 1, 2026");
    expect(fmt(parseLocalDate("2026-03-01"))).toBe("Mar 1, 2026");
  });

  it("leaves a string that already carries a time alone", () => {
    const d = parseLocalDate("2026-08-05T22:50");
    expect(d.getDate()).toBe(5);
    expect(d.getHours()).toBe(22);
    expect(d.getMinutes()).toBe(50);
  });

  it("does not mistake a timestamp with an explicit zone for a local one", () => {
    // Regex must not match, so the constructor's own UTC handling applies.
    expect(parseLocalDate("2026-08-05T02:50:00Z").toISOString()).toBe("2026-08-05T02:50:00.000Z");
  });
});

// The mirror image: producing a date string rather than reading one. Here the
// trap is `toISOString()`, which after ~20:00 EDT already says tomorrow.
describe("todayISO", () => {
  it("uses the local calendar day, not the UTC one", () => {
    // 2026-08-05 22:50 local — in EDT that is already Aug 6 in UTC.
    const evening = new Date(2026, 7, 5, 22, 50);
    expect(todayISO(evening)).toBe("2026-08-05");
  });

  it("zero-pads month and day", () => {
    expect(todayISO(new Date(2026, 0, 9, 12, 0))).toBe("2026-01-09");
  });

  it("agrees with the local getters for right now", () => {
    const now = new Date();
    const [y, m, d] = todayISO().split("-").map(Number);
    expect([y, m, d]).toEqual([now.getFullYear(), now.getMonth() + 1, now.getDate()]);
  });

  it("round-trips through parseLocalDate", () => {
    const d = new Date(2026, 7, 5, 22, 50);
    expect(parseLocalDate(todayISO(d)).getDate()).toBe(5);
  });
});
