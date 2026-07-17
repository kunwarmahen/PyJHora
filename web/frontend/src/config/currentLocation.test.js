import {
  detectOffsetHours,
  dismissZone,
  isZoneDismissed,
  locationPrompt,
  zoneDisplayName,
  zoneLabel,
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

describe("zoneDisplayName", () => {
  it("names the zone the way a person would, never the city", () => {
    // The point of the whole helper: "Chicago" is a claim about where the user
    // is (Milwaukee is also America/Chicago); "Central Time" is only a claim
    // about their clock, which is the part we actually know.
    expect(zoneDisplayName("America/Chicago", "en")).toBe("Central Time");
    expect(zoneDisplayName("Asia/Kolkata", "en")).toBe("India Standard Time");
    expect(zoneDisplayName("Asia/Kathmandu", "en")).toBe("Nepal Time");
  });

  it("is stable across DST, unlike the 'long' name", () => {
    // longGeneric gives "Central Time" year-round rather than flipping between
    // Central Daylight and Central Standard — the banner must not look like it
    // changed its mind twice a year.
    expect(zoneDisplayName("America/Chicago", "en")).not.toMatch(/Daylight|Standard/);
  });

  it("resolves the zone's real region, not the name it happens to carry", () => {
    // America/Indiana/Indianapolis IS Eastern Time. Labelling it by its city
    // would have said "Indianapolis" and told the user nothing about the clock.
    expect(zoneDisplayName("America/Indiana/Indianapolis", "en")).toBe("Eastern Time");
  });

  it("is localised by Intl, needing no translation table of our own", () => {
    expect(zoneDisplayName("America/Chicago", "hi")).not.toBe("Central Time");
    expect(zoneDisplayName("America/Chicago", "hi")).toBeTruthy();
  });

  it("falls back to the raw zone rather than a blank or an invented name", () => {
    expect(zoneDisplayName("Mars/Olympus", "en")).toBe("Mars/Olympus");
  });

  it("is null only when there is no zone at all", () => {
    expect(zoneDisplayName(null)).toBeNull();
    expect(zoneDisplayName("")).toBeNull();
  });
});

describe("zoneLabel", () => {
  it("pairs the name with the offset it is on right now", () => {
    expect(zoneLabel("America/Chicago", -5, "en")).toBe("Central Time (UTC−5)");
    expect(zoneLabel("Asia/Kolkata", 5.5, "en")).toBe("India Standard Time (UTC+5.5)");
  });

  it("uses a real minus sign, not a hyphen", () => {
    // U+2212. A hyphen next to a digit reads as a dash in most UI fonts.
    expect(zoneLabel("America/Chicago", -5, "en")).toContain("−5");
  });

  it("drops the offset rather than printing a broken one", () => {
    expect(zoneLabel("America/Chicago", undefined, "en")).toBe("Central Time");
    expect(zoneLabel("America/Chicago", null, "en")).toBe("Central Time");
  });

  it("is null when there is no zone", () => {
    expect(zoneLabel(null, -5)).toBeNull();
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
