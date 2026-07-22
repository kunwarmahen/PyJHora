import {
  LayoutDashboard,
  Calendar,
  Clock,
  Orbit,
  CalendarClock,
  Moon,
  Sparkles,
  Heart,
  MessageCircle,
  Grid3x3,
  GitCompareArrows,
  GraduationCap,
  CalendarDays,
  Clock4,
  Bird,
  Crosshair,
  Timer,
  Settings,
  CalendarCheck,
  HelpCircle,
  Sun,
  Waypoints,
  GanttChartSquare,
  Gauge,
  Aperture,
  Gem,
  History,
  CalendarRange,
  Home,
  FileText,
  Compass,
  Layers,
  Globe,
  Star,
  BookText,
  ScrollText,
} from "lucide-react";

/**
 * The single source of truth for "what features exist and where do they live".
 *
 * The NavDrawer, the Dashboard tiles and the Essentials/Everything filter all
 * render from THIS list. Before it existed each of those kept its own hard-coded
 * copy and they had drifted (the drawer and the dashboard disagreed about which
 * features existed at all). Add a feature here once and it shows up everywhere.
 *
 * Fields:
 *   key       i18n key stem — `nav.<key>` for the drawer label and
 *             `dashboard.features.<key>.{title,description}` for the tile.
 *   path      route, matching App.js.
 *   Icon      lucide component (NOT an element) so each surface picks its size.
 *   tier      "simple"   → visible in Essentials mode (and in Everything)
 *             "advanced" → only in Everything mode. Never *gated*: an advanced
 *                          path still renders in Essentials mode if you deep-link
 *                          to it, it just isn't advertised. See <AdvancedNotice>.
 *   group     coarse grouping, for the drawer's section headings.
 *   navOnly   in the drawer but not a dashboard tile (Dashboard, Settings).
 *   gradient  dashboard tile icon wash.
 *
 * Ordering here is the render order everywhere.
 */
export const FEATURES = [
  {
    key: "dashboard",
    path: "/dashboard",
    Icon: LayoutDashboard,
    tier: "simple",
    group: "core",
    navOnly: true,
  },
  {
    key: "birthChart",
    path: "/birth-chart",
    Icon: Calendar,
    tier: "simple",
    group: "core",
    gradient: "linear-gradient(135deg, #FF9933 0%, #FFB347 100%)",
  },
  {
    key: "ask",
    path: "/ask-astrologer",
    Icon: MessageCircle,
    tier: "simple",
    group: "core",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #E34234 100%)",
  },
  {
    key: "dailyDigest",
    path: "/daily-digest",
    Icon: Sun,
    tier: "simple",
    group: "core",
    gradient: "linear-gradient(135deg, #FF9933 0%, #E27B5A 100%)",
  },
  {
    key: "compatibility",
    path: "/compatibility",
    Icon: Heart,
    tier: "simple",
    group: "core",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #FFB347 100%)",
  },
  {
    key: "dhasa",
    path: "/dhasa",
    Icon: Clock,
    tier: "simple",
    group: "timing",
    gradient: "linear-gradient(135deg, #2D3561 0%, #5A5F7A 100%)",
  },
  {
    key: "transit",
    path: "/transit",
    Icon: Orbit,
    tier: "simple",
    group: "timing",
    gradient: "linear-gradient(135deg, #5A5F7A 0%, #D4AF37 100%)",
  },
  {
    key: "remedies",
    path: "/remedies",
    Icon: Gem,
    tier: "simple",
    group: "core",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #D4AF37 100%)",
  },
  {
    key: "lifeReport",
    path: "/life-report",
    Icon: ScrollText,
    tier: "simple",
    group: "core",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #2D3561 100%)",
  },
  {
    key: "history",
    path: "/history",
    Icon: History,
    tier: "simple",
    group: "core",
    gradient: "linear-gradient(135deg, #FF9933 0%, #2D3561 100%)",
  },
  {
    key: "settings",
    path: "/settings",
    Icon: Settings,
    tier: "simple",
    group: "core",
    navOnly: true,
  },

  // ── Everything-only from here down ────────────────────────────────────────
  {
    key: "gochara",
    path: "/gochara",
    Icon: Orbit,
    tier: "advanced",
    group: "timing",
    gradient: "linear-gradient(135deg, #2D3561 0%, #C97B54 100%)",
  },
  {
    key: "nakshatra",
    path: "/nakshatra",
    Icon: Star,
    tier: "advanced",
    group: "analysis",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #FF9933 100%)",
  },
  {
    key: "ephemeris",
    path: "/ephemeris",
    Icon: CalendarRange,
    tier: "advanced",
    group: "reference",
    gradient: "linear-gradient(135deg, #2D3561 0%, #D4AF37 100%)",
  },
  {
    key: "bhava",
    path: "/bhava",
    Icon: Home,
    tier: "advanced",
    group: "analysis",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #D4AF37 100%)",
  },
  {
    key: "report",
    path: "/report",
    Icon: FileText,
    tier: "advanced",
    group: "analysis",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #FF9933 100%)",
  },
  {
    key: "varshaphal",
    path: "/varshaphal",
    Icon: CalendarClock,
    tier: "advanced",
    group: "timing",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #2D3561 100%)",
  },
  {
    key: "tithiPravesha",
    path: "/tithi-pravesha",
    Icon: Moon,
    tier: "advanced",
    group: "timing",
    gradient: "linear-gradient(135deg, #2D3561 0%, #FF9933 100%)",
  },
  {
    key: "almanac",
    path: "/almanac",
    Icon: CalendarDays,
    tier: "advanced",
    group: "reference",
    gradient: "linear-gradient(135deg, #FFB347 0%, #D4AF37 100%)",
  },
  {
    key: "fortnightlyDigest",
    path: "/fortnightly-digest",
    Icon: CalendarDays,
    tier: "advanced",
    group: "timing",
    gradient: "linear-gradient(135deg, #F0883E 0%, #D4AF37 100%)",
  },
  {
    key: "monthlyDigest",
    path: "/monthly-digest",
    Icon: CalendarRange,
    tier: "advanced",
    group: "timing",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #B5651D 100%)",
  },
  {
    key: "muhurta",
    path: "/muhurta",
    Icon: CalendarCheck,
    tier: "advanced",
    group: "timing",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #FFB347 100%)",
  },
  {
    key: "prashna",
    path: "/prashna",
    Icon: HelpCircle,
    tier: "advanced",
    group: "tools",
    gradient: "linear-gradient(135deg, #2D3561 0%, #5A5F7A 100%)",
  },
  {
    key: "timeline",
    path: "/timeline",
    Icon: GanttChartSquare,
    tier: "advanced",
    group: "timing",
    gradient: "linear-gradient(135deg, #2D3561 0%, #E27B5A 100%)",
  },
  {
    key: "strength",
    path: "/strength",
    Icon: Gauge,
    tier: "advanced",
    group: "analysis",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #2E9E5B 100%)",
  },
  {
    key: "sadeSati",
    path: "/sade-sati",
    Icon: Aperture,
    tier: "advanced",
    group: "timing",
    gradient: "linear-gradient(135deg, #5A5F7A 0%, #B23A48 100%)",
  },
  {
    key: "bhrigu",
    path: "/bhrigu-markers",
    Icon: Waypoints,
    tier: "advanced",
    group: "analysis",
    gradient: "linear-gradient(135deg, #5A5F7A 0%, #D4AF37 100%)",
  },
  {
    key: "nadi",
    path: "/nadi",
    Icon: ScrollText,
    tier: "advanced",
    group: "analysis",
    gradient: "linear-gradient(135deg, #3A3F5A 0%, #C97B4A 100%)",
  },
  {
    key: "panchaPakshi",
    path: "/pancha-pakshi",
    Icon: Bird,
    tier: "advanced",
    group: "tools",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #FFB347 100%)",
  },
  {
    key: "sarvatobhadra",
    path: "/chakras",
    Icon: Grid3x3,
    tier: "advanced",
    group: "tools",
    gradient: "linear-gradient(135deg, #FF9933 0%, #2D3561 100%)",
  },
  {
    key: "sensitivePoints",
    path: "/sensitive-points",
    Icon: Crosshair,
    tier: "advanced",
    group: "analysis",
    gradient: "linear-gradient(135deg, #2D3561 0%, #D4AF37 100%)",
  },
  {
    key: "vedicClock",
    path: "/vedic-clock",
    Icon: Timer,
    tier: "advanced",
    group: "reference",
    gradient: "linear-gradient(135deg, #5A5F7A 0%, #FF9933 100%)",
  },
  {
    key: "kp",
    path: "/kp",
    Icon: Compass,
    tier: "advanced",
    group: "analysis",
    gradient: "linear-gradient(135deg, #2D3561 0%, #5A5F7A 100%)",
  },
  {
    key: "jaimini",
    path: "/jaimini",
    Icon: Layers,
    tier: "advanced",
    group: "analysis",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #E34234 100%)",
  },
  {
    key: "now",
    path: "/now",
    Icon: Globe,
    tier: "advanced",
    group: "reference",
    gradient: "linear-gradient(135deg, #5A5F7A 0%, #D4AF37 100%)",
  },
  {
    key: "advanced",
    path: "/advanced",
    Icon: Sparkles,
    tier: "advanced",
    group: "analysis",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #E27B5A 100%)",
  },
  {
    key: "compare",
    path: "/compare",
    Icon: GitCompareArrows,
    tier: "advanced",
    group: "tools",
    gradient: "linear-gradient(135deg, #2D3561 0%, #E27B5A 100%)",
  },
  {
    key: "rectify",
    path: "/rectify",
    Icon: Clock4,
    tier: "advanced",
    group: "tools",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #2D3561 100%)",
  },
  {
    key: "learn",
    path: "/learn",
    Icon: GraduationCap,
    tier: "advanced",
    group: "tools",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #D4AF37 100%)",
  },
  {
    key: "journal",
    path: "/journal",
    Icon: BookText,
    tier: "advanced",
    group: "tools",
    gradient: "linear-gradient(135deg, #C97B54 0%, #2D3561 100%)",
  },
];

/**
 * Extra search keywords per feature, for the dashboard's type-to-filter launcher.
 * These are intuitive words a user might type that AREN'T already in the tile's
 * title/description (which the filter also matches) — e.g. "marriage" should
 * find Compatibility, "gemstone" should find Remedies. English-only on purpose:
 * they're a hit-rate booster layered on top of the (localized) title+description
 * match, not a translation. Add to this as features grow. Keyed by feature key.
 */
export const FEATURE_ALIASES = {
  birthChart: "kundali rasi natal horoscope lagna ascendant d1 d9 navamsa planets",
  ask: "chat question ai astrologer talk advice",
  dailyDigest: "today daily forecast horoscope of the day",
  compatibility: "marriage match matching guna milan ashtakoot dashakoota partner spouse relationship love porutham mangal dosha",
  dhasa: "dasha vimshottari vimsottari mahadasha bhukti antardasha period timing",
  transit: "gochara current planets movement now",
  remedies: "gemstone gem stone mantra upaya parihara donation deity",
  lifeReport: "report full life story chapters narrative",
  history: "saved readings past previous history",
  gochara: "transit phala moon vedha",
  nakshatra: "star birth star janma tarabala constellation",
  ephemeris: "planet positions longitude tables ephemeris",
  bhava: "house cusp chart placidus sripati equal kp bhava",
  report: "pdf print full report export",
  varshaphal: "annual solar return tajaka year varsha muntha",
  tithiPravesha: "annual lunar return tithi pravesha",
  almanac: "panchang panchanga calendar festival vratha eclipse hora hijri",
  fortnightlyDigest: "paksha fortnight two week",
  monthlyDigest: "maasa month lunar month",
  muhurta: "auspicious time electional choghadiya panchaka good time",
  prashna: "horary question kp prashna",
  timeline: "life timeline dasha transit events",
  strength: "shadbala planetary strength bhava bala vimsopaka",
  sadeSati: "saturn shani seven and half sade sati kantaka ashtama",
  bhrigu: "nadi bhrigu bindu markers yearly progression",
  nadi: "karaka significator nadi timing conjunction",
  panchaPakshi: "bird timing five birds pancha pakshi",
  sarvatobhadra: "chakra kota kaala tripataki vedha sarvatobhadra",
  sensitivePoints: "sphuta saham argala sensitive points",
  vedicClock: "clock ghati hora retrograde vakra vedic clock",
  kp: "krishnamurti sub lord significator ruling planets horary kp system",
  jaimini: "chara karaka karakamsa swamsa argala jaimini",
  now: "chart of the moment now current instant",
  compare: "compare two charts synastry side by side",
  rectify: "birth time correction rectification unknown time",
  learn: "quiz learn practice study lesson",
  journal: "diary log events astro journal notes",
  advanced: "more all everything advanced tools",
};

/** Features to advertise for a ui mode. "advanced" mode shows everything. */
export const visibleFeatures = (uiMode) =>
  uiMode === "advanced" ? FEATURES : FEATURES.filter((f) => f.tier === "simple");

/** The registry entry owning a route, or undefined. */
export const featureForPath = (path) => FEATURES.find((f) => f.path === path);

/** Is this route advertised in the given mode? Unknown routes count as visible
 * (login, profile-selection, /share/... — pages the registry deliberately omits,
 * which must never be treated as hidden-advanced). */
export const isFeatureVisible = (path, uiMode) => {
  const feature = featureForPath(path);
  return !feature || feature.tier === "simple" || uiMode === "advanced";
};
