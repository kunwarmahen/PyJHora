import { signNumOf, signAtVisualHouse } from "./chartPosition";

describe("signNumOf", () => {
  it("reads sign_num", () => {
    expect(signNumOf({ sign_num: 4, house: 12, sign_name: "Cancer" })).toBe(4);
  });

  it("falls back to the 0-based rasi of a pre-rename payload", () => {
    expect(signNumOf({ rasi: 3, sign_name: "Cancer" })).toBe(4);
  });

  it("never reads a sign out of `house`", () => {
    // The bug this module exists to prevent: a lagna's `house` is always 1, so
    // treating it as the sign numbers every cell with its own house number.
    expect(signNumOf({ house: 1, sign_name: "Taurus" })).toBeNull();
    expect(signNumOf({ house: 12, sign_name: "Cancer" })).toBeNull();
  });

  it("returns null rather than a guess for junk", () => {
    expect(signNumOf(null)).toBeNull();
    expect(signNumOf({})).toBeNull();
    expect(signNumOf({ sign_num: 0 })).toBeNull();
    expect(signNumOf({ sign_num: 13 })).toBeNull();
    expect(signNumOf({ sign_num: "4" })).toBeNull();
  });
});

describe("signAtVisualHouse", () => {
  it("counts the diagram round from the lagna's cell", () => {
    expect(signAtVisualHouse(2, 1)).toBe(2); // Taurus lagna → 1st house is Taurus
    expect(signAtVisualHouse(2, 12)).toBe(1); // …and the 12th is Aries
    expect(signAtVisualHouse(11, 3)).toBe(1); // wraps past Pisces
  });

  it("propagates an unknown lagna instead of numbering the houses", () => {
    expect(signAtVisualHouse(null, 1)).toBeNull();
  });
});
