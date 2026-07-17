// Shared Jyotish display constants.

import NAME_LOCALES, { NAME_ORDER } from "./nameLocales.generated";

// The English names below are derived from the generated name tables rather than spelled
// out here, so English and the hi/sa translations can't drift apart. To show a name in
// the user's language, don't reach for these — call useLocalizeName() from i18n/localizeName.

// Planet name -> two-letter abbreviation.
export const PLANET_ABBR = NAME_LOCALES.en.grahasAbbr;

// Rasi / sign names, index 0 = Aries … 11 = Pisces
export const RASI_NAMES = NAME_ORDER.rasis;

// Two-letter sign abbreviations, same order as RASI_NAMES
export const RASI_ABBR = NAME_ORDER.rasis.map((n) => NAME_LOCALES.en.rasisAbbr[n]);

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

// Per-question varga hints: when the user's question mentions one of these
// keywords, the Ask page suggests adding the relevant divisional chart(s) to the
// AI context. Each rule maps a topic to its classical vargas (D-factors).
export const VARGA_SUGGESTIONS = [
  { topic: "career", vargas: [10], keywords: ["career", "job", "work", "profession", "business", "promotion", "office", "boss"] },
  { topic: "marriage", vargas: [9, 7], keywords: ["marriage", "spouse", "wife", "husband", "wedding", "relationship", "partner", "love", "divorce"] },
  { topic: "children", vargas: [7], keywords: ["children", "child", "kids", "progeny", "pregnancy", "conceive", "son", "daughter"] },
  { topic: "wealth", vargas: [2], keywords: ["wealth", "money", "finance", "income", "riches", "savings", "prosperity"] },
  { topic: "property", vargas: [4], keywords: ["property", "house", "home", "land", "real estate", "vehicle", "comfort"] },
  { topic: "education", vargas: [24], keywords: ["education", "study", "studies", "exam", "college", "degree", "learning", "academic"] },
  { topic: "siblings", vargas: [3], keywords: ["sibling", "siblings", "brother", "sister", "courage"] },
  { topic: "parents", vargas: [12], keywords: ["parents", "father", "mother", "ancestry", "lineage"] },
  { topic: "spirituality", vargas: [20], keywords: ["spiritual", "spirituality", "moksha", "worship", "mantra", "guru", "devotion"] },
  { topic: "health", vargas: [30], keywords: ["health", "disease", "illness", "ailment", "sickness", "longevity", "accident"] },
];

// Distinct line colours per aspecting graha, used when drawing graha-drishti
// (aspect) lines over the Rasi chart.
export const ASPECT_COLORS = {
  Sun: "#e8820c",
  Moon: "#5c6b7a",
  Mars: "#cc3300",
  Mercury: "#2e7d32",
  Jupiter: "#b8860b",
  Venus: "#c2185b",
  Saturn: "#37474f",
  Rahu: "#5e35b1",
  Ketu: "#8d6e63",
};

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
