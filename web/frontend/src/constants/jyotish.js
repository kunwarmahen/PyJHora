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

// Ayanamsa options (must mirror the backend's SUPPORTED_AYANAMSAS).
export const DEFAULT_AYANAMSA = "LAHIRI";
export const AYANAMSAS = [
  { value: "LAHIRI", label: "Lahiri (Chitrapaksha)" },
  { value: "TRUE_CITRA", label: "True Chitra Paksha" },
  { value: "KP", label: "Krishnamurti (KP)" },
  { value: "RAMAN", label: "B. V. Raman" },
  { value: "YUKTESHWAR", label: "Sri Yukteshwar" },
  { value: "TRUE_PUSHYA", label: "True Pushya" },
  { value: "FAGAN", label: "Fagan / Bradley" },
];
