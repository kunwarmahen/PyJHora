import {
  detectOffsetHours,
  dismissZone,
  isZoneDismissed,
  locationPrompt,
  zoneCity,
} from "./currentLocation";

const chicago = { place: "Chicago", latitude: 41.88, longitude: -87.63, timezone: "America/Chicago" };

describe("locationPrompt", () => {
  afterEach(() => localStorage.clear());

  describe("with a location already set", () => {
    it("says nothing when the browser agrees with it", () => {
      expect(
        locationPrompt({ location: chicago, zone: "America/Chicago", offset: -6 })
      ).toBeNull();
    });

    it("suggests an update when the browser is somewhere else", () => {
      expect(locationPrompt({ location: chicago, zone: "Europe/London", offset: 0 })).toEqual({
        kind: "moved",
        zone: "Europe/London",
      });
    });

    it("ignores the birth offset entirely once a location is set", () => {
      // The stored location is the answer; birth data must not second-guess it.
      expect(
        locationPrompt({ location: chicago, birthOffset: 5.5, zone: "America/Chicago", offset: -6 })
      ).toBeNull();
    });

    it("says nothing across a DST shift, because the zone is unchanged", () => {
      // The whole reason we store a zone: Chicago in July is -5, not -6, and
      // that must not read as "you moved".
      expect(
        locationPrompt({ location: chicago, zone: "America/Chicago", offset: -5 })
      ).toBeNull();
    });
  });

  describe("with no location set", () => {
    it("offers to set one when the browser disagrees with the birth profile", () => {
      // THE case: born in India (+5.5), living in Chicago (-6).
      expect(locationPrompt({ birthOffset: 5.5, zone: "America/Chicago", offset: -6 })).toEqual({
        kind: "unset",
        zone: "America/Chicago",
      });
    });

    it("says nothing to someone who still lives where they were born", () => {
      expect(
        locationPrompt({ birthOffset: 5.5, zone: "Asia/Kolkata", offset: 5.5 })
      ).toBeNull();
    });

    it("says nothing when there is no birth offset to compare against", () => {
      expect(locationPrompt({ zone: "America/Chicago", offset: -6 })).toBeNull();
    });
  });

  it("says nothing when the browser won't name a zone", () => {
    expect(locationPrompt({ location: chicago, zone: null, offset: -6 })).toBeNull();
  });

  it("stays quiet about a zone the user dismissed", () => {
    dismissZone("Europe/London");
    expect(locationPrompt({ location: chicago, zone: "Europe/London", offset: 0 })).toBeNull();
  });

  it("still speaks up for a DIFFERENT zone after one was dismissed", () => {
    // Dismissing "I'm in London this week" must not silence a later real move.
    dismissZone("Europe/London");
    expect(locationPrompt({ location: chicago, zone: "Asia/Tokyo", offset: 9 })).toEqual({
      kind: "moved",
      zone: "Asia/Tokyo",
    });
  });

  it("never throws on junk", () => {
    expect(locationPrompt()).toBeNull();
    expect(locationPrompt({ location: {}, zone: "Asia/Tokyo", offset: 9 })).toBeNull();
  });
});

describe("isZoneDismissed", () => {
  afterEach(() => localStorage.clear());

  it("is false for a zone never dismissed", () => {
    expect(isZoneDismissed("Asia/Tokyo")).toBe(false);
  });

  it("remembers each dismissed zone independently", () => {
    dismissZone("Europe/London");
    dismissZone("Asia/Tokyo");
    expect(isZoneDismissed("Europe/London")).toBe(true);
    expect(isZoneDismissed("Asia/Tokyo")).toBe(true);
    expect(isZoneDismissed("America/Chicago")).toBe(false);
  });

  it("is false rather than a throw when the store is corrupt", () => {
    localStorage.setItem("location_prompt_dismissed", "{not json");
    expect(isZoneDismissed("Asia/Tokyo")).toBe(false);
    expect(() => dismissZone("Asia/Tokyo")).not.toThrow();
  });

  it("ignores an empty zone", () => {
    expect(isZoneDismissed(null)).toBe(false);
    expect(isZoneDismissed("")).toBe(false);
  });
});

describe("zoneCity", () => {
  it("names the zone's city", () => {
    expect(zoneCity("America/Chicago")).toBe("Chicago");
    expect(zoneCity("Asia/Kolkata")).toBe("Kolkata");
  });

  it("turns underscores into spaces for display", () => {
    expect(zoneCity("America/New_York")).toBe("New York");
  });

  it("takes the last segment of a three-part zone", () => {
    expect(zoneCity("America/Argentina/Buenos_Aires")).toBe("Buenos Aires");
  });

  it("is null when the zone names no city", () => {
    // The banner falls back to showing the raw zone rather than a bad guess.
    ["Etc/GMT+2", "UTC", "", null, "Asia"].forEach((z) => expect(zoneCity(z)).toBeNull());
  });

  it("agrees with the server's representative_place, which is the real lookup", () => {
    // This is display only — timezones.representative_place decides what's saved,
    // and verifies it against coordinates. Drift here is cosmetic, not a bug.
    expect(zoneCity("America/Indiana/Indianapolis")).toBe("Indianapolis");
  });
});

describe("detectOffsetHours", () => {
  it("reports offsets east-positive, inverting the JS convention", () => {
    // getTimezoneOffset returns minutes WEST of UTC: India is -330 for +5.5.
    // Getting this backwards would place every US user in Asia.
    const spy = jest.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(-330);
    expect(detectOffsetHours()).toBe(5.5);
    spy.mockReturnValue(360); // US Central, standard time
    expect(detectOffsetHours()).toBe(-6);
    spy.mockRestore();
  });
});
