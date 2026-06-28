// Shared Jyotish display constants.

export const PLANET_ABBR = {
  Sun: "Su",
  Moon: "Mo",
  Mars: "Ma",
  Mercury: "Me",
  Jupiter: "Ju",
  Venus: "Ve",
  Saturn: "Sa",
  Rahu: "Ra",
  Ketu: "Ke",
};

// Rasi / sign names, index 0 = Aries … 11 = Pisces
export const RASI_NAMES = [
  "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
  "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
];

// Two-letter sign abbreviations, same order as RASI_NAMES
export const RASI_ABBR = [
  "Ar", "Ta", "Ge", "Cn", "Le", "Vi",
  "Li", "Sc", "Sg", "Cp", "Aq", "Pi",
];

// Divisional (varga) charts for the picker (must mirror the backend's
// SUPPORTED_VARGAS). `value` is the divisional-chart factor.
export const DEFAULT_VARGA = 9;
export const VARGAS = [
  { value: 1, code: "D1", name: "Rasi", significance: "Body, overall life" },
  { value: 2, code: "D2", name: "Hora", significance: "Wealth, prosperity" },
  { value: 3, code: "D3", name: "Drekkana", significance: "Siblings, courage" },
  { value: 4, code: "D4", name: "Chaturthamsa", significance: "Fortune, property, home" },
  { value: 7, code: "D7", name: "Saptamsa", significance: "Children, progeny" },
  { value: 9, code: "D9", name: "Navamsa", significance: "Spouse, dharma, fortune" },
  { value: 10, code: "D10", name: "Dasamsa", significance: "Career, status, achievements" },
  { value: 12, code: "D12", name: "Dwadasamsa", significance: "Parents, ancestry" },
  { value: 16, code: "D16", name: "Shodasamsa", significance: "Vehicles, comforts, luxuries" },
  { value: 20, code: "D20", name: "Vimsamsa", significance: "Spiritual pursuits, worship" },
  { value: 24, code: "D24", name: "Chaturvimsamsa", significance: "Education, learning" },
  { value: 27, code: "D27", name: "Bhamsa", significance: "Strengths and weaknesses" },
  { value: 30, code: "D30", name: "Trimsamsa", significance: "Misfortunes, adversity" },
  { value: 40, code: "D40", name: "Khavedamsa", significance: "Auspicious & inauspicious effects" },
  { value: 45, code: "D45", name: "Akshavedamsa", significance: "General character, conduct" },
  { value: 60, code: "D60", name: "Shashtiamsa", significance: "Past karma, overall refinement" },
];

// Ayanamsa options (must mirror the backend's SUPPORTED_AYANAMSAS).
export const DEFAULT_AYANAMSA = "TRUE_CITRA";
export const AYANAMSAS = [
  { value: "TRUE_CITRA", label: "True Chitra Paksha (Lahiri)" },
  { value: "LAHIRI", label: "Lahiri (traditional)" },
  { value: "KP", label: "Krishnamurti (KP)" },
  { value: "RAMAN", label: "B. V. Raman" },
  { value: "YUKTESHWAR", label: "Sri Yukteshwar" },
  { value: "TRUE_PUSHYA", label: "True Pushya" },
  { value: "FAGAN", label: "Fagan / Bradley" },
];
