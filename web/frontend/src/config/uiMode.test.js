import { resolveUiMode } from "./uiMode";

// The grandfathering rule is the part of the Essentials/Everything split that
// can silently do harm: get it wrong and an existing user opens the app one day
// to find most of their pages gone.
describe("resolveUiMode", () => {
  beforeEach(() => localStorage.clear());

  it("starts a brand-new user in Essentials", () => {
    expect(resolveUiMode()).toBe("simple");
  });

  it("honours an explicit stored choice", () => {
    localStorage.setItem("ui_mode", "advanced");
    expect(resolveUiMode()).toBe("advanced");
    localStorage.setItem("ui_mode", "simple");
    expect(resolveUiMode()).toBe("simple");
  });

  it("grandfathers a browser that used the app before the split", () => {
    // No ui_mode, but settings from prior use → this person already knows the
    // full app; don't shrink it under them.
    localStorage.setItem("ayanamsa", "TRUE_CITRA");
    expect(resolveUiMode()).toBe("advanced");
  });

  it.each(["chartStyle", "ai_model", "ai_provider_type", "panchanga_system"])(
    "treats a stored %s as prior use",
    (key) => {
      localStorage.setItem(key, "x");
      expect(resolveUiMode()).toBe("advanced");
    }
  );

  it("ignores a junk stored value rather than trusting it", () => {
    localStorage.setItem("ui_mode", "banana");
    expect(resolveUiMode()).toBe("simple");
  });

  it("prefers the explicit choice over the prior-use guess", () => {
    localStorage.setItem("ayanamsa", "TRUE_CITRA");
    localStorage.setItem("ui_mode", "simple");
    expect(resolveUiMode()).toBe("simple");
  });

  it("records its answer so it is decided once, not re-derived", () => {
    expect(resolveUiMode()).toBe("simple");
    expect(localStorage.getItem("ui_mode")).toBe("simple");
  });

  // The regression that made the write-back necessary: prior-use keys are ones
  // that ordinary use CREATES (Ask AI writes ai_model, and Ask AI ships in
  // Essentials). Without a recorded decision, a new user who simply used the app
  // would be silently promoted to Everything on their next visit.
  it("does not promote a new user to Everything once they use the app", () => {
    expect(resolveUiMode()).toBe("simple");
    localStorage.setItem("ai_model", "gemma3:12b"); // what Ask AI does
    expect(resolveUiMode()).toBe("simple");
  });
});
