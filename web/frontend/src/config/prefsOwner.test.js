import { claimPrefsOwner, PREFS_OWNER_STORAGE_KEY } from "./prefsOwner";

beforeEach(() => localStorage.clear());

describe("claimPrefsOwner", () => {
  it("grandfathers an unstamped cache to the first user who claims it", () => {
    // Every install predating the stamp: the cached settings really are theirs.
    expect(claimPrefsOwner("asha")).toBe(false);
    expect(localStorage.getItem(PREFS_OWNER_STORAGE_KEY)).toBe("asha");
  });

  it("keeps the cache across repeat logins by the same user", () => {
    claimPrefsOwner("asha");
    expect(claimPrefsOwner("asha")).toBe(false);
  });

  it("reports a foreign cache when a different user signs in", () => {
    claimPrefsOwner("asha");
    expect(claimPrefsOwner("ravi")).toBe(true);
    expect(localStorage.getItem(PREFS_OWNER_STORAGE_KEY)).toBe("ravi");
  });

  it("re-stamps on a switch back, so the next switch is caught too", () => {
    claimPrefsOwner("asha");
    claimPrefsOwner("ravi");
    expect(claimPrefsOwner("asha")).toBe(true);
    expect(claimPrefsOwner("asha")).toBe(false);
  });

  it("claims nothing without a username (still loading the profile)", () => {
    claimPrefsOwner("asha");
    expect(claimPrefsOwner(undefined)).toBe(false);
    expect(localStorage.getItem(PREFS_OWNER_STORAGE_KEY)).toBe("asha");
  });
});
