// Short, plain-language definitions of common Jyotish (Vedic astrology) terms.
// Keyed by the term as displayed; GlossaryTerm looks up case-insensitively.
export const GLOSSARY = {
  Lagna:
    "The ascendant — the zodiac sign rising on the eastern horizon at birth; the 1st house and the foundation of the chart.",
  Rasi: "A zodiac sign (1/12 of the zodiac, 30°). The Rasi chart (D1) is the main birth chart.",
  Navamsa:
    "The D9 divisional chart (each sign split into 9). Used for marriage, dharma and inner strength.",
  Nakshatra:
    "One of the 27 lunar mansions (each 13°20'). Governs finer personality and dasha timing.",
  Pada: "A quarter (1/4) of a nakshatra, 3°20' wide; ties a nakshatra to a navamsa sign.",
  Dasha:
    "A planetary period that times when results unfold. Vimsottari is the most common 120-year system.",
  Bhukti: "A sub-period (Antardasha) within a Maha Dasha.",
  Antara: "A sub-sub-period (Pratyantar) within a Bhukti.",
  Sookshma: "A fine sub-period within an Antara.",
  Vimsottari: "The principal 120-year nakshatra-based dasha system.",
  Ashtottari: "A conditional 108-year nakshatra dasha system.",
  Yogini: "A 36-year nakshatra dasha of the eight Yoginis.",
  Narayana: "A rasi (sign) dasha measured from the lagna; a Jaimini system.",
  Kalachakra: "The 'wheel of time' rasi dasha, seeded from the Moon's navamsa.",
  Yoga: "A specific planetary combination that produces a defined result.",
  Dosha: "An affliction or flaw in the chart (e.g. Mangal/Kuja, Kaal Sarpa).",
  Gochara: "Transits — the current movement of planets, read over the natal chart.",
  Varga: "A divisional chart (e.g. D9, D10) that magnifies a specific area of life.",
  Ashtakavarga: "A bindu (point) scoring system; Sarva combines all to show each sign's strength.",
  Bhinna: "The per-contributor Ashtakavarga table (one planet's bindus per sign).",
  Sarva: "The combined Ashtakavarga total per sign (sums to 337 across the zodiac).",
  Shadbala: "The 'six-fold strength' of a planet, measured in rupas against a required minimum.",
  Arudha: "A reflected/perceived point of a house (e.g. Arudha Lagna = how others see you).",
  Karaka: "A significator. Chara karakas (Jaimini) are assigned by planetary longitude.",
  Atma: "Atma Karaka — the planet at the highest degree; significator of the soul/self.",
  Upagraha: "A 'sub-planet' or shadowy point (e.g. Gulika, Maandi, Dhuma).",
  Gulika: "A malefic upagraha (son of Saturn) used in timing and affliction analysis.",
  Maandi: "An upagraha closely related to Gulika; a sensitive malefic point.",
  Panchanga: "The five limbs of the Vedic almanac: tithi, vaara, nakshatra, yoga, karana.",
  Tithi: "A lunar day — the angle between Sun and Moon in 12° steps.",
  Vaara: "The weekday, each ruled by a planet.",
  Karana: "Half of a tithi; one of eleven used in muhurta (electional) timing.",
  Ayanamsa:
    "The precession offset between the tropical and sidereal zodiacs (e.g. Lahiri, True Chitra).",
};

// case-insensitive lookup
export const lookupGlossary = (key) => {
  if (!key) return null;
  if (GLOSSARY[key]) return GLOSSARY[key];
  const lower = String(key).toLowerCase();
  const hit = Object.keys(GLOSSARY).find((k) => k.toLowerCase() === lower);
  return hit ? GLOSSARY[hit] : null;
};
