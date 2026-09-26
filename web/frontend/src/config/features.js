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
 *   group     section this feature belongs to — a key from FEATURE_GROUPS below.
 *             The dashboard and the drawer both render section headings from it.
 *   navOnly   in the drawer but not a dashboard tile (Dashboard, Settings).
 *   footer    drawer renders it in the footer with the other account-level
 *             actions (Help, Logout) instead of in the feature list.
 *   gradient  dashboard tile icon wash.
 *
 * Ordering here is the render order everywhere: features are listed section by
 * section in FEATURE_GROUPS order, and within a section in the order an
 * astrologer would actually reach for them.
 */
/**
 * The sections features are clustered into, in render order.
 *
 * The order is the order of a reading, not an alphabet and not the order these
 * pages happened to get built: you cast the chart, you read the chart, you time
 * it with dashas and transits, you consult the calendar for a moment to act,
 * and only then do you talk about partners and remedies. Tiles that an
 * astrologer reaches for in the same breath now sit next to each other.
 *
 *   key    matches `group` on a feature; labels come from `nav.groups.<key>`
 *          (heading) and `nav.groups.<key>Hint` (the dashboard's one-liner).
 */
export const FEATURE_GROUPS = [
  { key: "start" },
  { key: "chart" },
  { key: "timing" },
  { key: "calendar" },
  { key: "relationships" },
  { key: "practice" },
];

export const FEATURES = [
  // ═══ Start here — the chart itself, the assistant, and today ════════════════
  {
    key: "dashboard",
    path: "/dashboard",
    Icon: LayoutDashboard,
    tier: "simple",
    group: "start",
    navOnly: true,
  },
  {
    key: "birthChart",
    path: "/birth-chart",
    Icon: Calendar,
    tier: "simple",
    group: "start",
    gradient: "linear-gradient(135deg, #FF9933 0%, #FFB347 100%)",
  },
  {
    key: "ask",
    path: "/ask-astrologer",
    Icon: MessageCircle,
    tier: "simple",
    group: "start",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #E34234 100%)",
  },
  {
    key: "dailyDigest",
    path: "/daily-digest",
    Icon: Sun,
    tier: "simple",
    group: "start",
    gradient: "linear-gradient(135deg, #FF9933 0%, #E27B5A 100%)",
  },
  // ═══ Read the chart — houses, then grahas, then the special systems ═════════
  {
    key: "bhava",
    path: "/bhava",
    Icon: Home,
    tier: "advanced",
    group: "chart",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #D4AF37 100%)",
  },
  {
    key: "nakshatra",
    path: "/nakshatra",
    Icon: Star,
    tier: "advanced",
    group: "chart",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #FF9933 100%)",
  },
  {
    key: "strength",
    path: "/strength",
    Icon: Gauge,
    tier: "advanced",
    group: "chart",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #2E9E5B 100%)",
  },
  {
    key: "advanced",
    path: "/advanced",
    Icon: Sparkles,
    tier: "advanced",
    group: "chart",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #E27B5A 100%)",
  },
  {
    key: "sensitivePoints",
    path: "/sensitive-points",
    Icon: Crosshair,
    tier: "advanced",
    group: "chart",
    gradient: "linear-gradient(135deg, #2D3561 0%, #D4AF37 100%)",
  },
  {
    key: "jaimini",
    path: "/jaimini",
    Icon: Layers,
    tier: "advanced",
    group: "chart",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #E34234 100%)",
  },
  {
    key: "kp",
    path: "/kp",
    Icon: Compass,
    tier: "advanced",
    group: "chart",
    gradient: "linear-gradient(135deg, #2D3561 0%, #5A5F7A 100%)",
  },
  {
    key: "nadi",
    path: "/nadi",
    Icon: ScrollText,
    tier: "advanced",
    group: "chart",
    gradient: "linear-gradient(135deg, #3A3F5A 0%, #C97B4A 100%)",
  },
  {
    key: "bhrigu",
    path: "/bhrigu-markers",
    Icon: Waypoints,
    tier: "advanced",
    group: "chart",
    gradient: "linear-gradient(135deg, #5A5F7A 0%, #D4AF37 100%)",
  },
  {
    key: "lifeReport",
    path: "/life-report",
    Icon: ScrollText,
    tier: "simple",
    group: "chart",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #2D3561 100%)",
  },
  {
    key: "report",
    path: "/report",
    Icon: FileText,
    tier: "advanced",
    group: "chart",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #FF9933 100%)",
  },
  // ═══ Timing — dashas first, then transits over them ═════════════════════════
  {
    key: "dhasa",
    path: "/dhasa",
    Icon: Clock,
    tier: "simple",
    group: "timing",
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
    key: "transit",
    path: "/transit",
    Icon: Orbit,
    tier: "simple",
    group: "timing",
    gradient: "linear-gradient(135deg, #5A5F7A 0%, #D4AF37 100%)",
  },
  {
    key: "gochara",
    path: "/gochara",
    Icon: Orbit,
    tier: "advanced",
    group: "timing",
    gradient: "linear-gradient(135deg, #2D3561 0%, #C97B54 100%)",
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
  // ═══ Calendar & muhurta — the sky's own clock, and picking a moment ═════════
  {
    key: "fortnightlyDigest",
    path: "/fortnightly-digest",
    Icon: CalendarDays,
    tier: "advanced",
    group: "calendar",
    gradient: "linear-gradient(135deg, #F0883E 0%, #D4AF37 100%)",
  },
  {
    key: "monthlyDigest",
    path: "/monthly-digest",
    Icon: CalendarRange,
    tier: "advanced",
    group: "calendar",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #B5651D 100%)",
  },
  {
    key: "almanac",
    path: "/almanac",
    Icon: CalendarDays,
    tier: "advanced",
    group: "calendar",
    gradient: "linear-gradient(135deg, #FFB347 0%, #D4AF37 100%)",
  },
  {
    key: "muhurta",
    path: "/muhurta",
    Icon: CalendarCheck,
    tier: "advanced",
    group: "calendar",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #FFB347 100%)",
  },
  {
    key: "panchaPakshi",
    path: "/pancha-pakshi",
    Icon: Bird,
    tier: "advanced",
    group: "calendar",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #FFB347 100%)",
  },
  {
    key: "sarvatobhadra",
    path: "/chakras",
    Icon: Grid3x3,
    tier: "advanced",
    group: "calendar",
    gradient: "linear-gradient(135deg, #FF9933 0%, #2D3561 100%)",
  },
  {
    key: "vedicClock",
    path: "/vedic-clock",
    Icon: Timer,
    tier: "advanced",
    group: "calendar",
    gradient: "linear-gradient(135deg, #5A5F7A 0%, #FF9933 100%)",
  },
  {
    key: "now",
    path: "/now",
    Icon: Globe,
    tier: "advanced",
    group: "calendar",
    gradient: "linear-gradient(135deg, #5A5F7A 0%, #D4AF37 100%)",
  },
  {
    key: "ephemeris",
    path: "/ephemeris",
    Icon: CalendarRange,
    tier: "advanced",
    group: "calendar",
    gradient: "linear-gradient(135deg, #2D3561 0%, #D4AF37 100%)",
  },
  // ═══ Relationships ══════════════════════════════════════════════════════════
  {
    key: "compatibility",
    path: "/compatibility",
    Icon: Heart,
    tier: "simple",
    group: "relationships",
    gradient: "linear-gradient(135deg, #D4AF37 0%, #FFB347 100%)",
  },
  {
    key: "compare",
    path: "/compare",
    Icon: GitCompareArrows,
    tier: "advanced",
    group: "relationships",
    gradient: "linear-gradient(135deg, #2D3561 0%, #E27B5A 100%)",
  },
  // ═══ Remedies & your own practice ═══════════════════════════════════════════
  {
    key: "remedies",
    path: "/remedies",
    Icon: Gem,
    tier: "simple",
    group: "practice",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #D4AF37 100%)",
  },
  {
    key: "prashna",
    path: "/prashna",
    Icon: HelpCircle,
    tier: "advanced",
    group: "practice",
    gradient: "linear-gradient(135deg, #2D3561 0%, #5A5F7A 100%)",
  },
  {
    key: "journal",
    path: "/journal",
    Icon: BookText,
    tier: "advanced",
    group: "practice",
    gradient: "linear-gradient(135deg, #C97B54 0%, #2D3561 100%)",
  },
  {
    key: "history",
    path: "/history",
    Icon: History,
    tier: "simple",
    group: "practice",
    gradient: "linear-gradient(135deg, #FF9933 0%, #2D3561 100%)",
  },
  {
    key: "learn",
    path: "/learn",
    Icon: GraduationCap,
    tier: "advanced",
    group: "practice",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #D4AF37 100%)",
  },
  {
    key: "rectify",
    path: "/rectify",
    Icon: Clock4,
    tier: "advanced",
    group: "practice",
    gradient: "linear-gradient(135deg, #E27B5A 0%, #2D3561 100%)",
  },
  {
    key: "settings",
    path: "/settings",
    Icon: Settings,
    tier: "simple",
    group: "practice",
    navOnly: true,
    footer: true,
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
  birthChart:
    "kundali rasi natal horoscope lagna ascendant d1 d9 navamsa planets" +
    " yoga yogas dosha doshas raja yoga aspects drishti divisional varga vargas",
  ask: "chat question ai astrologer talk advice",
  dailyDigest: "today daily forecast horoscope of the day",
  compatibility:
    "marriage match matching guna milan ashtakoot dashakoota partner spouse relationship love porutham mangal dosha" +
    " kuja dosha manglik seventh house 7th house",
  dhasa: "dasha vimshottari vimsottari mahadasha bhukti antardasha period timing",
  transit:
    "gochara current planets movement now arudha arudh aroodha lagna al upapada ul pada" +
    " padas bhava arudha nakshatra gochara star stars transit star tara tarabala tara bala" +
    " nakshatra transit star window when does it end how long",
  remedies: "gemstone gem stone mantra upaya parihara donation deity",
  lifeReport: "report full life story chapters narrative",
  history:
    "saved readings past previous history outcome outcomes did this land track record accuracy hit rate came true verdict",
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
  muhurta:
    "auspicious time electional choghadiya panchaka good time kaala vela gulika yamaganda rahu kalam tara bala tarabala chandra bala chandrabala lagna shuddhi suddhi personal muhurta abhijit hora",
  prashna: "horary question kp prashna",
  timeline: "life timeline dasha transit events upcoming what's coming forward calendar alerts",
  strength: "shadbala planetary strength bhava bala vimsopaka ishta kashta",
  sadeSati: "saturn shani seven and half sade sati kantaka ashtama",
  bhrigu: "nadi bhrigu bindu markers yearly progression",
  nadi: "karaka significator nadi timing conjunction",
  panchaPakshi: "bird timing five birds pancha pakshi",
  sarvatobhadra: "chakra kota kaala tripataki vedha sarvatobhadra",
  sensitivePoints:
    "sphuta saham argala sensitive points special lagna upagraha hora ghati bhava vighati varnada gulika maandi kaala mrityu dhuma vyatipata parivesha indrachapa upaketu sree indu bhrigu bindu pranapada kunda mandi",
  vedicClock: "clock ghati hora retrograde vakra vedic clock",
  kp: "krishnamurti sub lord significator ruling planets horary kp system",
  jaimini: "chara karaka karakamsa swamsa argala jaimini arudha pada upapada atmakaraka amatyakaraka darakaraka",
  now: "chart of the moment now current instant",
  compare: "compare two charts synastry side by side",
  rectify: "birth time correction rectification unknown time",
  learn: "quiz learn practice study lesson",
  journal: "diary log events astro journal notes",
  advanced:
    "more all everything advanced tools arudha arudh aroodha pada padas upapada al ul" +
    " sarvashtakavarga bhinnashtakavarga bindu bindus longevity ayu ayurdaya planetary conditions" +
    " combust combustion retrograde avastha avasthas friendship friendships maitri",
};

/**
 * Sub-features that live INSIDE a tile — a tab or a picker option — rather than
 * as their own tile. The dashboard filter searches these too and deep-links
 * straight to them, so typing "Sudarshana" finds the Sudarshana Chakra dasha
 * even though it's buried in the Dhasa picker.
 *
 *   label     the sub-tool's own name (a technical proper noun — kept here
 *             rather than i18n since PyJHora doesn't localize most of them; the
 *             localized part is the "in <Tile>" wrapper, from the parent tile).
 *   parent    owning feature key — supplies the "in <Tile>" label and the icon.
 *   keywords  English search terms (matched alongside the label + parent title).
 *   to        deep-link. Tab pages read `?tab=` (handled by useTabs, so no page
 *             change needed); the Dhasa picker reads `?system=`.
 *
 * Dhasa `system` values are the backend SUPPORTED_DASHAS keys, verbatim.
 */
export const FEATURE_SUBITEMS = [
  // ── Birth Chart tabs (§15 tab split) — the most-searched content in the app
  //    lives behind these, so each gets its own deep-link. ──
  {
    label: "Yogas & Doshas",
    parent: "birthChart",
    to: "/birth-chart?tab=yogas",
    keywords:
      "yoga yogas raja yoga rajayoga dhana yoga gajakesari pancha mahapurusha ruchaka bhadra hamsa malavya sasa" +
      " budhaditya neechabhanga viparita dosha doshas kaal sarp kala sarpa kalasarpa mangal manglik kuja pitru" +
      " guru chandal combinations",
  },
  {
    label: "Aspects",
    parent: "birthChart",
    to: "/birth-chart?tab=aspects",
    keywords: "aspects aspect drishti graha drishti rasi drishti sight",
  },
  {
    label: "Divisional charts (vargas)",
    parent: "birthChart",
    to: "/birth-chart?tab=advanced",
    keywords:
      "divisional varga vargas shodasavarga d2 d3 d4 d7 d10 d12 d16 d20 d24 d27 d30 d40 d45 d60" +
      " hora drekkana chaturthamsa saptamsa dasamsa dashamsa dwadasamsa shodasamsa vimsamsa" +
      " chaturvimsamsa bhamsa trimsamsa khavedamsa akshavedamsa shashtyamsa career",
  },
  {
    label: "Birth Panchanga",
    parent: "birthChart",
    to: "/birth-chart?tab=panchanga",
    keywords: "panchanga panchang birth tithi vara karana yoga birth day weekday",
  },
  {
    label: "Nakshatra & Lagna",
    parent: "birthChart",
    to: "/birth-chart?tab=nakshatra",
    keywords: "nakshatra pada birth star janma lagna ascendant rising sign",
  },
  // ── Strength tabs ──
  {
    label: "Shadbala",
    parent: "strength",
    to: "/strength?tab=shadbala",
    keywords: "shadbala six fold strength sthana dig kaala chesta naisargika drik rupas",
  },
  {
    label: "Bhava Bala",
    parent: "strength",
    to: "/strength?tab=bhava",
    keywords: "bhava bala house strength",
  },
  {
    label: "Vimsopaka Bala",
    parent: "strength",
    to: "/strength?tab=vimsopaka",
    keywords: "vimsopaka vimshopaka varga strength twenty point",
  },
  // ── Compatibility workspace + matching systems ──
  {
    label: "7th House (marriage)",
    parent: "compatibility",
    to: "/compatibility?tab=seventh",
    keywords: "seventh house 7th house spouse marriage partner d9 navamsa",
  },
  {
    label: "Marriage timeline",
    parent: "compatibility",
    to: "/compatibility?tab=timeline",
    keywords: "marriage timing timeline when will i marry dasha overlap saturn",
  },
  {
    label: "Mangal Dosha",
    parent: "compatibility",
    to: "/compatibility?system=mangal",
    keywords: "mangal dosha manglik kuja dosha mars dosha chevvai",
  },
  {
    label: "Dashakoota (10 poruthams)",
    parent: "compatibility",
    to: "/compatibility?system=dashakoota",
    keywords: "dashakoota dasa porutham ten poruthams south indian matching",
  },
  // ── KP horary ──
  {
    label: "KP Horary (1–249)",
    parent: "kp",
    to: "/kp?tab=horary",
    keywords: "kp horary prashna number 249 question",
  },
  // ── Chart Deep-Dive sections (one scrolling page, no tabs) ──
  {
    label: "Ashtakavarga",
    parent: "advanced",
    to: "/advanced",
    keywords: "ashtakavarga sarvashtakavarga bhinnashtakavarga bindu bindus sav bav",
  },
  {
    label: "Longevity (Ayu)",
    parent: "advanced",
    to: "/advanced",
    keywords: "longevity ayu ayurdaya lifespan vitality",
  },
  {
    label: "Planetary conditions & Avasthas",
    parent: "advanced",
    to: "/advanced",
    keywords:
      "planetary conditions combust combustion retrograde exalted debilitated avastha avasthas baladi jagradadi deeptadi states",
  },
  {
    label: "Planetary friendships",
    parent: "advanced",
    to: "/advanced",
    keywords: "friendship friendships maitri friend enemy neutral panchadha",
  },
  // ── Dhasa picker: the conditional / rasi dasha systems ──
  {
    label: "Sudarshana Chakra Dasha",
    parent: "dhasa",
    to: "/dhasa?system=sudharsana_chakra",
    keywords: "sudarshana sudarsana chakra wheel three charts",
  },
  {
    label: "Ashtottari Dasha",
    parent: "dhasa",
    to: "/dhasa?system=ashtottari",
    keywords: "ashtottari 108",
  },
  { label: "Yogini Dasha", parent: "dhasa", to: "/dhasa?system=yogini", keywords: "yogini" },
  {
    label: "Kalachakra Dasha",
    parent: "dhasa",
    to: "/dhasa?system=kalachakra",
    keywords: "kalachakra kaalachakra wheel of time",
  },
  {
    label: "Narayana Dasha",
    parent: "dhasa",
    to: "/dhasa?system=narayana",
    keywords: "narayana pada rasi jaimini",
  },
  {
    label: "Chara Dasha",
    parent: "dhasa",
    to: "/dhasa?system=chara",
    keywords: "chara jaimini rasi movable",
  },
  {
    label: "Sthira Dasha",
    parent: "dhasa",
    to: "/dhasa?system=sthira",
    keywords: "sthira fixed rasi",
  },
  {
    label: "Trikona Dasha",
    parent: "dhasa",
    to: "/dhasa?system=trikona",
    keywords: "trikona trine rasi",
  },
  {
    label: "Drig Dasha",
    parent: "dhasa",
    to: "/dhasa?system=drig",
    keywords: "drig aspectual rasi jaimini",
  },
  {
    label: "Sudasa Dasha",
    parent: "dhasa",
    to: "/dhasa?system=sudasa",
    keywords: "sudasa sree lagna rasi",
  },
  {
    label: "Kendradhi Rasi Dasha",
    parent: "dhasa",
    to: "/dhasa?system=kendradhi_rasi",
    keywords: "kendradhi rasi kendra",
  },
  {
    label: "Shodasottari Dasha",
    parent: "dhasa",
    to: "/dhasa?system=shodasottari",
    keywords: "shodasottari 116",
  },
  {
    label: "Dwadasottari Dasha",
    parent: "dhasa",
    to: "/dhasa?system=dwadasottari",
    keywords: "dwadasottari 112",
  },
  {
    label: "Panchottari Dasha",
    parent: "dhasa",
    to: "/dhasa?system=panchottari",
    keywords: "panchottari 105",
  },
  {
    label: "Shatabdika Dasha",
    parent: "dhasa",
    to: "/dhasa?system=shatabdika",
    keywords: "shatabdika 100",
  },
  {
    label: "Shashtihayani Dasha",
    parent: "dhasa",
    to: "/dhasa?system=shashtihayani",
    keywords: "shashtihayani shastihayani shashti sama shasti 60 sun in lagna",
  },
  {
    label: "Chaturaaseeti Sama Dasha",
    parent: "dhasa",
    to: "/dhasa?system=chaturaaseeti_sama",
    keywords: "chaturaaseeti chathuraaseethi sama 84",
  },
  {
    label: "Dwisatpathi Dasha",
    parent: "dhasa",
    to: "/dhasa?system=dwisatpathi",
    keywords: "dwisatpathi dvisaptati sama 112",
  },
  // ── Chakras page: the individual chakras (tab deep-links via useTabs) ──
  {
    label: "Kota Chakra",
    parent: "sarvatobhadra",
    to: "/chakras?tab=kota",
    keywords: "kota fort protection siege",
  },
  {
    label: "Kaala Chakra",
    parent: "sarvatobhadra",
    to: "/chakras?tab=kaala",
    keywords: "kaala kala directions wheel",
  },
  // ── Transits: the star-level view of the same gochara (§75) ──
  {
    label: "Nakshatra gochara (transit stars)",
    parent: "transit",
    to: "/transit",
    keywords:
      "nakshatra gochara transit star stars tara tarabala tara bala star window" +
      " which star is saturn in how long does this transit last star ingress",
  },
  {
    label: "Tripataki Chakra",
    parent: "sarvatobhadra",
    to: "/chakras?tab=tripataki",
    keywords: "tripataki vedha moon lagna",
  },
  // ── Life Timeline: the forward calendar (§70), a tab deep-link ──
  {
    label: "What's coming (forward calendar)",
    parent: "timeline",
    to: "/timeline?tab=upcoming",
    keywords:
      "upcoming coming next events alerts forecast calendar when does my dasha change sade sati end ingress station retrograde eclipse reminders notify",
  },
  // ── Sensitive Points page: the three sub-tools (tab deep-links) ──
  {
    label: "Special Points",
    parent: "sensitivePoints",
    to: "/sensitive-points?tab=special",
    keywords:
      "special lagna upagraha hora lagna ghati lagna bhava lagna vighati varnada gulika maandi kaala mrityu artha prahara yama ghantaka dhuma vyatipata parivesha indrachapa upaketu sree indu bhrigu bindu pranapada kunda",
  },
  {
    label: "Sahams",
    parent: "sensitivePoints",
    to: "/sensitive-points?tab=sahams",
    keywords: "sahams 36 arabic parts lots",
  },
  {
    label: "Argala",
    parent: "sensitivePoints",
    to: "/sensitive-points?tab=argala",
    keywords: "argala intervention obstruction",
  },
  {
    label: "Sphutas",
    parent: "sensitivePoints",
    to: "/sensitive-points?tab=sphuta",
    keywords: "sphuta sensitive longitudes beeja kshetra",
  },
];

/** Features to advertise for a ui mode. "advanced" mode shows everything. */
export const visibleFeatures = (uiMode) =>
  uiMode === "advanced" ? FEATURES : FEATURES.filter((f) => f.tier === "simple");

/**
 * Split an already-filtered feature list into its sections, in FEATURE_GROUPS
 * order. Sections with nothing left in them are dropped — Essentials mode empties
 * Calendar & Muhurta entirely, and a search for "dasha" empties most of them.
 * Callers pass whatever list they're rendering (mode-filtered, search-filtered,
 * drawer minus its footer links) so the grouping never contradicts the filter.
 */
export const groupedFeatures = (features) =>
  FEATURE_GROUPS.map((group) => ({
    ...group,
    features: features.filter((f) => f.group === group.key),
  })).filter((section) => section.features.length > 0);

/** The registry entry owning a route, or undefined. */
export const featureForPath = (path) => FEATURES.find((f) => f.path === path);

/** The registry entry with this key, or undefined (for sub-feature parents). */
export const featureForKey = (key) => FEATURES.find((f) => f.key === key);

/** Is this route advertised in the given mode? Unknown routes count as visible
 * (login, profile-selection, /share/... — pages the registry deliberately omits,
 * which must never be treated as hidden-advanced). */
export const isFeatureVisible = (path, uiMode) => {
  const feature = featureForPath(path);
  return !feature || feature.tier === "simple" || uiMode === "advanced";
};

/**
 * The dashboard's type-to-filter launcher, as a pure function so its coverage is
 * testable (features.test.js pins the terms people actually type). `t` supplies
 * the localized tile title/description; aliases and sub-item keywords are
 * English. Every whitespace token must appear somewhere in an entry's haystack.
 * Sub-items ignore Essentials/Everything: a deep-link must never dead-end just
 * because its parent tile is hidden.
 */
export const searchFeatures = (features, query, t) => {
  const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!tokens.length) return { tiles: features, subs: [] };
  const hit = (parts) => {
    const hay = parts.join(" ").toLowerCase();
    return tokens.every((tok) => hay.includes(tok));
  };
  const tiles = features.filter((f) =>
    hit([
      t(`dashboard.features.${f.key}.title`),
      t(`dashboard.features.${f.key}.description`),
      FEATURE_ALIASES[f.key] || "",
    ])
  );
  const subs = FEATURE_SUBITEMS.filter((s) => {
    const parent = featureForKey(s.parent);
    return hit([s.label, s.keywords || "", parent ? t(`dashboard.features.${parent.key}.title`) : ""]);
  });
  return { tiles, subs };
};
