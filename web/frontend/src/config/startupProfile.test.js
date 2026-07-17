import {
  readLastProfileId,
  readStartupProfileMode,
  resolveStartupProfile,
  SELECTED_PROFILE_STORAGE_KEY,
  STARTUP_PROFILE_DEFAULT,
  STARTUP_PROFILE_MODES,
  STARTUP_PROFILE_STORAGE_KEY,
} from "./startupProfile";

const mine = { _id: "a", profile_name: "Mine" };
const spouse = { _id: "b", profile_name: "Spouse", is_default: true };
const child = { _id: "c", profile_name: "Child" };
const all = [mine, spouse, child];

describe("resolveStartupProfile", () => {
  it("resumes the last-used profile", () => {
    expect(resolveStartupProfile(all, { mode: "resume", lastId: "c" })).toBe(child);
  });

  it("falls back to the default profile when there is no last-used one", () => {
    expect(resolveStartupProfile(all, { mode: "resume", lastId: null })).toBe(spouse);
  });

  it("prefers the last-used profile over the default one", () => {
    expect(resolveStartupProfile(all, { mode: "resume", lastId: "a" })).toBe(mine);
  });

  it("shows the picker when several profiles exist and none is default", () => {
    expect(resolveStartupProfile([mine, child], { mode: "resume", lastId: null })).toBeNull();
  });

  it("opens the only profile there is rather than a one-card picker", () => {
    expect(resolveStartupProfile([mine], { mode: "resume", lastId: null })).toBe(mine);
  });

  it("shows the picker in ask mode even when it could resolve one", () => {
    expect(resolveStartupProfile(all, { mode: "ask", lastId: "c" })).toBeNull();
  });

  it("returns the FRESH record, not the caller's cached copy", () => {
    // The cache holds a pre-rename snapshot; resuming must show the new name.
    const fresh = [{ _id: "a", profile_name: "Renamed" }];
    expect(resolveStartupProfile(fresh, { mode: "resume", lastId: "a" })).toBe(fresh[0]);
  });

  it("shows the picker when the last-used profile was deleted elsewhere", () => {
    // Deleted on another device: resuming into it would open a dashboard for a
    // chart the server no longer has.
    expect(resolveStartupProfile([mine, child], { mode: "resume", lastId: "gone" })).toBeNull();
  });

  it("resolves to the default when the last-used profile was deleted elsewhere", () => {
    expect(resolveStartupProfile(all, { mode: "resume", lastId: "gone" })).toBe(spouse);
  });

  it("shows the picker for a user with no profiles yet", () => {
    expect(resolveStartupProfile([], { mode: "resume", lastId: "a" })).toBeNull();
  });

  it("shows the picker rather than throwing on junk in place of a profile list", () => {
    [undefined, null, "", 0, {}].forEach((junk) => {
      expect(resolveStartupProfile(junk, { mode: "resume", lastId: "a" })).toBeNull();
    });
  });

  it("treats a missing mode as resume, since only 'ask' suppresses resuming", () => {
    expect(resolveStartupProfile(all)).toBe(spouse);
  });
});

describe("readStartupProfileMode", () => {
  afterEach(() => localStorage.clear());

  it("defaults to resuming when nothing has been chosen", () => {
    expect(readStartupProfileMode()).toBe(STARTUP_PROFILE_DEFAULT);
  });

  it.each(STARTUP_PROFILE_MODES)("reads back a stored %s", (mode) => {
    localStorage.setItem(STARTUP_PROFILE_STORAGE_KEY, mode);
    expect(readStartupProfileMode()).toBe(mode);
  });

  it("falls back to the default for a junk stored value", () => {
    localStorage.setItem(STARTUP_PROFILE_STORAGE_KEY, "picker");
    expect(readStartupProfileMode()).toBe(STARTUP_PROFILE_DEFAULT);
  });
});

describe("readLastProfileId", () => {
  afterEach(() => localStorage.clear());

  it("is null when no profile was ever selected", () => {
    expect(readLastProfileId()).toBeNull();
  });

  it("reads the id out of the cached profile", () => {
    localStorage.setItem(SELECTED_PROFILE_STORAGE_KEY, JSON.stringify(child));
    expect(readLastProfileId()).toBe("c");
  });

  it("is null rather than a throw when the cache is corrupt", () => {
    // Any user can edit localStorage, and an older build may have written a
    // different shape. A throw here would block login.
    localStorage.setItem(SELECTED_PROFILE_STORAGE_KEY, "{not json");
    expect(readLastProfileId()).toBeNull();
    localStorage.setItem(SELECTED_PROFILE_STORAGE_KEY, JSON.stringify({ name: "no id" }));
    expect(readLastProfileId()).toBeNull();
  });
});
