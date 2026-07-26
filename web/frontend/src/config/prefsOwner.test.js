import {
  claimPrefsOwner,
  purgeCachedUserState,
  resetPrefsOwnerClaim,
  PREFS_OWNER_STORAGE_KEY,
} from "./prefsOwner";

// Each test is a fresh page load: empty storage, no memoised verdict.
beforeEach(() => {
  localStorage.clear();
  resetPrefsOwnerClaim();
});

// A sign-in in a new tab/page: the module-level memo starts over, the storage
// stamp does not.
const newPageLoad = () => resetPrefsOwnerClaim();

describe("claimPrefsOwner", () => {
  it("grandfathers an unstamped cache to the first user who claims it", () => {
    // Every install predating the stamp: the cached settings really are theirs.
    expect(claimPrefsOwner("asha")).toBe(false);
    expect(localStorage.getItem(PREFS_OWNER_STORAGE_KEY)).toBe("asha");
  });

  it("keeps the cache across repeat logins by the same user", () => {
    claimPrefsOwner("asha");
    newPageLoad();
    expect(claimPrefsOwner("asha")).toBe(false);
  });

  it("reports a foreign cache when a different user signs in", () => {
    claimPrefsOwner("asha");
    newPageLoad();
    expect(claimPrefsOwner("ravi")).toBe(true);
    expect(localStorage.getItem(PREFS_OWNER_STORAGE_KEY)).toBe("ravi");
  });

  it("gives every context the same verdict for one login", () => {
    // AuthContext purges, SettingsContext resets, ProfileContext drops the
    // selected chart — all off this one call. Whoever asked first would
    // otherwise stamp the browser and leave the rest seeing their own cache.
    claimPrefsOwner("asha");
    newPageLoad();
    expect(claimPrefsOwner("ravi")).toBe(true);
    expect(claimPrefsOwner("ravi")).toBe(true);
    expect(claimPrefsOwner("ravi")).toBe(true);
  });

  it("re-evaluates on a switch back in a later page load", () => {
    claimPrefsOwner("asha");
    newPageLoad();
    claimPrefsOwner("ravi");
    newPageLoad();
    expect(claimPrefsOwner("asha")).toBe(true);
    newPageLoad();
    expect(claimPrefsOwner("asha")).toBe(false);
  });

  it("claims nothing without a username (still loading the profile)", () => {
    claimPrefsOwner("asha");
    newPageLoad();
    expect(claimPrefsOwner(undefined)).toBe(false);
    expect(localStorage.getItem(PREFS_OWNER_STORAGE_KEY)).toBe("asha");
  });
});

describe("purgeCachedUserState", () => {
  it("drops the previous account's cached settings and chart", () => {
    localStorage.setItem("ai_model", "gemini-3.5-flash");
    localStorage.setItem("ai_provider_type", "gemini");
    localStorage.setItem("selectedProfile", JSON.stringify({ profile_name: "Asha" }));
    localStorage.setItem("ayanamsa", "LAHIRI");

    purgeCachedUserState();

    expect(localStorage.getItem("ai_model")).toBeNull();
    expect(localStorage.getItem("ai_provider_type")).toBeNull();
    expect(localStorage.getItem("selectedProfile")).toBeNull();
    expect(localStorage.getItem("ayanamsa")).toBeNull();
  });

  it("purges by exception, so a key added later is covered too", () => {
    localStorage.setItem("some_page_cache_invented_next_year", "x");
    expect(purgeCachedUserState()).toContain("some_page_cache_invented_next_year");
  });

  it("keeps the arriving session and the stamp", () => {
    // The new user's tokens are stored before their profile loads: purging them
    // would sign them straight back out, and dropping the stamp would re-arm the
    // whole thing on their next login.
    localStorage.setItem("access_token", "new-user-jwt");
    localStorage.setItem("refresh_token", "new-user-refresh");
    localStorage.setItem(PREFS_OWNER_STORAGE_KEY, "ravi");

    purgeCachedUserState();

    expect(localStorage.getItem("access_token")).toBe("new-user-jwt");
    expect(localStorage.getItem("refresh_token")).toBe("new-user-refresh");
    expect(localStorage.getItem(PREFS_OWNER_STORAGE_KEY)).toBe("ravi");
  });
});
