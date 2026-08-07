import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Sun, Moon, Monitor } from "lucide-react";
import { useSettings } from "../contexts/SettingsContext";
import { resolveTheme } from "../config/theme";
import { SITE_TITLE } from "../config/branding";
import "../styles/Landing.css";

/* Pricing shows only when REACT_APP_SHOW_PRICING === "true" (see .env). */
const SHOW_PRICING = process.env.REACT_APP_SHOW_PRICING === "true";

const THEME_ORDER = ["light", "dark", "system"];
const THEME_ICON = { light: Sun, dark: Moon, system: Monitor };
const THEME_LABEL = { light: "Light", dark: "Dark", system: "System" };

const BrandMark = () => (
  <svg className="brand-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <rect x="3" y="3" width="34" height="34" rx="3" className="stroke" strokeWidth="2" />
    <path d="M20 3 L37 20 L20 37 L3 20 Z" className="stroke" strokeWidth="1.6" />
    <path d="M3 3 L37 37 M37 3 L3 37" className="stroke" strokeWidth="1.2" opacity="0.7" />
  </svg>
);

const PLANS = [
  {
    name: "Free",
    desc: "For getting to know your chart.",
    price: "$0",
    per: "/forever",
    features: [
      "Birth chart + core vargas",
      "Panchanga & daily preview",
      "3 AI questions a day",
      "1 saved profile",
    ],
    cta: "Get started",
    ctaClass: "btn-outline",
  },
  {
    name: "Pro",
    featured: true,
    flag: "Most popular",
    desc: "For everyone who wants the whole picture.",
    monthly: "$9",
    annual: "$7",
    annualNote: "Billed $84/year",
    features: [
      "Everything in Free",
      "Unlimited AI readings & chat",
      "All dashas, transits & forecasts",
      "Full reports & PDF export",
      "Compatibility & daily digest",
      "5 saved profiles",
    ],
    cta: "Start 14-day free trial",
    ctaClass: "btn-primary",
  },
  {
    name: "Practitioner",
    desc: "For astrologers with real clients.",
    monthly: "$29",
    annual: "$23",
    annualNote: "Billed $276/year",
    features: [
      "Everything in Pro",
      "Unlimited client profiles",
      "KP, Jaimini & chakra tools",
      "API & MCP access",
      "Priority support",
    ],
    cta: "Start 14-day free trial",
    ctaClass: "btn-outline",
  },
];

const FEATURES = [
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
        <circle cx="12" cy="12" r="4" />
      </svg>
    ),
    title: "Readings you can check",
    body: "Ask anything about your chart and get a clear answer — each claim cited to a classical source, never invented.",
    tag: "AI · citations · plain language",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="4" y="4" width="16" height="16" rx="2" />
        <path d="M4 4 20 20M20 4 4 20" />
      </svg>
    ),
    title: "Your chart, sixteen ways",
    body: "North and South Indian charts, all sixteen divisional vargas, and bhava cusps in KP, Sripati, Placidus and Equal.",
    tag: "D1–D60 · bhava · cusps",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M12 6v6l4 2" />
        <circle cx="12" cy="12" r="9" />
      </svg>
    ),
    title: "Timing that means something",
    body: "Vimsottari and 40+ dasha systems, transit forecasts, and Ashtakavarga support scored on every planetary move.",
    tag: "dashas · transits · gochara",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="8" cy="9" r="3.5" />
        <circle cx="16" cy="9" r="3.5" />
        <path d="M4 20c0-3 2-5 4-5s4 2 4 5M12 20c0-3 2-5 4-5s4 2 4 5" />
      </svg>
    ),
    title: "Two charts, one story",
    body: "Ashtakoot and Dashakoota compatibility, seventh-house depth, and the years your two timelines actually overlap.",
    tag: "guna milan · marriage workspace",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M12 2 15 9l7 .5-5.5 4.5L20 21l-8-4.5L4 21l1.5-7L0 9.5 7 9z" transform="scale(0.9) translate(1.2 1.2)" />
      </svg>
    ),
    title: "KP, Jaimini & beyond",
    body: "Sub-lords and significators, Chara Karakas and Karakamsa, Sarvatobhadra and the classical chakras — all headless-accurate.",
    tag: "KP · Jaimini · chakras",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M12 3a9 9 0 1 0 9 9M12 3v9l6-4" />
      </svg>
    ),
    title: "A gentle daily rhythm",
    body: "Panchanga, muhurta windows, remedies, and a daily digest that lands in your inbox — so the sky checks in on you.",
    tag: "panchanga · muhurta · digest",
  },
];

const DEPTH_CHIPS = [
  "KP sub-lords & significators",
  "Jaimini Chara Karakas",
  "Ashtakavarga",
  "Shadbala & strengths",
  "Varshaphal & Tajaka",
  "Kota · Kaala · Tripataki chakras",
  "Prashna & horary (1–249)",
  "Ruling planets",
  "Multi-client profiles",
  "API & MCP access",
];

/** Slow, tilted spiral galaxy tucked into the hero's top-right corner + starfield. */
function makeStarfield(canvas, count, opts, reduce) {
  if (!canvas) return () => {};
  opts = opts || {};
  const ctx = canvas.getContext("2d");
  let stars = [], planets = [], gal = [], gx, gy, gR, w, h, dpr, raf;
  let t = 0;
  const tilt = -0.5, ct = Math.cos(tilt), st = Math.sin(tilt);

  function size() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = canvas.clientWidth; h = canvas.clientHeight;
    if (!w || !h) return;
    canvas.width = w * dpr; canvas.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    stars = [];
    for (let i = 0; i < count; i++) {
      stars.push({ x: Math.random() * w, y: Math.random() * h, r: Math.random() * 1.3 + 0.2,
        a: Math.random() * 0.6 + 0.2, tw: Math.random() * 0.02 + 0.004, ph: Math.random() * 6.28 });
    }
    if (opts.planets) {
      planets = [];
      const cols = ["#ff9f3d", "#ffc266", "#ff6a4d", "#9db8ff", "#ffe0a3"];
      for (let j = 0; j < 5; j++) {
        planets.push({ x: (0.12 + j * 0.19) * w, y: (0.2 + Math.sin(j) * 0.12) * h + h * 0.15,
          r: Math.random() * 1.6 + 1.6, c: cols[j] });
      }
    }
    if (opts.galaxy) {
      gx = w * 0.9; gy = h * 0.15; gR = Math.max(70, Math.min(w, h) * 0.17);
      gal = [];
      const N = 150, turns = 2.6;
      for (let k = 0; k < N; k++) {
        const frac = k / N, arm = k % 2;
        const theta = frac * turns * 6.283 + arm * Math.PI;
        const jit = (Math.random() - 0.5) * 0.5;
        const col = frac < 0.28 ? "#ffd9a0" : (frac < 0.6 ? "#f6ecd8" : "#9fb6ff");
        gal.push({ th: theta + jit, rad: frac * gR, sz: Math.random() * 1.1 + 0.5,
          c: col, a: (1 - frac) * 0.85 + 0.1, tw: Math.random() * 0.02 + 0.006, ph: Math.random() * 6.28 });
      }
    }
  }

  function drawGalaxy() {
    const core = ctx.createRadialGradient(gx, gy, 0, gx, gy, gR * 0.7);
    core.addColorStop(0, "rgba(255,210,150,0.55)");
    core.addColorStop(0.4, "rgba(255,170,90,0.16)");
    core.addColorStop(1, "transparent");
    ctx.globalAlpha = 1; ctx.fillStyle = core;
    ctx.beginPath(); ctx.arc(gx, gy, gR * 0.9, 0, 6.283); ctx.fill();
    const rot = t * 0.0011;
    for (let k = 0; k < gal.length; k++) {
      const p = gal[k], ang = p.th + rot;
      const px = Math.cos(ang) * p.rad, py = Math.sin(ang) * p.rad * 0.5;
      const x = gx + px * ct - py * st, y = gy + px * st + py * ct;
      ctx.globalAlpha = Math.max(0.05, p.a + Math.sin(t * p.tw * 60 + p.ph) * 0.2);
      ctx.beginPath(); ctx.arc(x, y, p.sz, 0, 6.283); ctx.fillStyle = p.c; ctx.fill();
    }
    ctx.globalAlpha = 0.95; ctx.fillStyle = "#fff3dd";
    ctx.beginPath(); ctx.arc(gx, gy, 2.4, 0, 6.283); ctx.fill();
  }

  function draw() {
    if (!w || !h) { raf = requestAnimationFrame(draw); return; }
    ctx.clearRect(0, 0, w, h);
    if (opts.galaxy) drawGalaxy();
    for (let i = 0; i < stars.length; i++) {
      const s = stars[i]; const a = s.a + Math.sin(t * s.tw * 60 + s.ph) * 0.25;
      ctx.globalAlpha = Math.max(0.05, Math.min(1, a));
      ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283); ctx.fillStyle = "#f4ecdb"; ctx.fill();
    }
    if (opts.planets) {
      for (let j = 0; j < planets.length; j++) {
        const p = planets[j]; ctx.globalAlpha = 0.9;
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4);
        g.addColorStop(0, p.c); g.addColorStop(1, "transparent");
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r * 4, 0, 6.283); ctx.fillStyle = g; ctx.fill();
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.283); ctx.fillStyle = p.c; ctx.fill();
      }
    }
    ctx.globalAlpha = 1; t += 1;
    if (!reduce) raf = requestAnimationFrame(draw);
  }

  function onResize() { cancelAnimationFrame(raf); size(); draw(); }
  size();
  draw();
  window.addEventListener("resize", onResize);
  return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", onResize); };
}

export const LandingPage = () => {
  const { settings, updateSetting } = useSettings();
  const [scrolled, setScrolled] = useState(false);
  const [annual, setAnnual] = useState(false);
  const rootRef = useRef(null);
  const heroCanvas = useRef(null);
  const finalCanvas = useRef(null);

  const pref = settings.theme || "system";
  const ThemeIcon = THEME_ICON[pref] || Monitor;
  const nextTheme = THEME_ORDER[(THEME_ORDER.indexOf(pref) + 1) % THEME_ORDER.length];
  const themeLabel = pref === "system" ? `${THEME_LABEL.system} · ${resolveTheme("system") === "dark" ? "Dark" : "Light"}` : THEME_LABEL[pref];

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Nav scroll state
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    // Reveal on scroll
    const revealEls = rootRef.current ? rootRef.current.querySelectorAll(".reveal") : [];
    let io;
    if (reduce) {
      revealEls.forEach((el) => el.classList.add("in"));
    } else {
      io = new IntersectionObserver((entries) => {
        entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
      }, { threshold: 0.14 });
      revealEls.forEach((el) => io.observe(el));
    }

    // Starfields
    const disposeHero = makeStarfield(heroCanvas.current, 150, { planets: true, galaxy: true }, reduce);
    const disposeFinal = makeStarfield(finalCanvas.current, 90, {}, reduce);

    return () => {
      window.removeEventListener("scroll", onScroll);
      if (io) io.disconnect();
      disposeHero();
      disposeFinal();
    };
  }, []);

  const priceOf = (plan) => (plan.price ? plan.price : annual ? plan.annual : plan.monthly);
  const perOf = (plan) => (plan.price ? plan.per : annual ? "/mo billed yearly" : "/month");

  return (
    <div className="landing" ref={rootRef}>
      {/* ===================== NAV ===================== */}
      <nav className={`nav${scrolled ? " scrolled" : ""}`}>
        <div className="nav-inner">
          <a className="brand" href="#top" aria-label={`${SITE_TITLE} home`}>
            <BrandMark />
            {SITE_TITLE}
          </a>
          <div className="nav-links">
            <a href="#features">Features</a>
            <a href="#how">How it works</a>
            <a href="#depth">For practitioners</a>
            {SHOW_PRICING && <a href="#pricing">Pricing</a>}
          </div>
          <div className="nav-right">
            <button
              type="button"
              className="theme-toggle"
              onClick={() => updateSetting("theme", nextTheme)}
              title={`Switch theme (next: ${THEME_LABEL[nextTheme]})`}
              aria-label={`Switch theme, currently ${themeLabel}`}
            >
              <ThemeIcon size={16} />
              <span className="tt-label">{themeLabel}</span>
            </button>
            <Link className="login-link" to="/login">Log in</Link>
            <Link className="btn btn-primary" to="/register">Get started free</Link>
          </div>
        </div>
      </nav>

      {/* ===================== HERO ===================== */}
      <header className="hero" id="top">
        <canvas className="stars" ref={heroCanvas} />
        <div className="wrap">
          <div className="hero-grid">
            <div className="hero-copy">
              <span className="eyebrow">ज्योतिष · the science of light</span>
              <h1>Read the sky like it<br />was <span className="accent">written for you.</span></h1>
              <p className="hero-sub">
                {SITE_TITLE} computes your Vedic chart to the arc-second with the Swiss Ephemeris,
                then explains it in plain language — with every answer traced back to the classical texts.
              </p>
              <div className="hero-cta">
                <Link className="btn btn-primary" to="/register">Get started free</Link>
                <a className="btn btn-ghost" href="#reading">See a sample reading</a>
              </div>
              <div className="hero-meta">
                <span>True&nbsp;Chitra ayanamsa</span>
                <span>Matches Jagannatha&nbsp;Hora</span>
                <span>50+ classical tools</span>
              </div>
            </div>

            <div className="chart-stage">
              <div className="chart-halo" />
              {/* North Indian (diamond) chart signature */}
              <svg className="vchart chart-north" viewBox="0 0 400 400" role="img" aria-label="A North Indian style Vedic birth chart">
                <rect className="frame" x="2" y="2" width="396" height="396" rx="6" />
                <path className="grid" d="M2 2 L398 398 M398 2 L2 398" />
                <path className="grid" d="M200 2 L398 200 L200 398 L2 200 Z" />
                <g className="hno" textAnchor="middle">
                  <text x="200" y="66">1</text><text x="100" y="40">2</text><text x="40" y="105">3</text>
                  <text x="116" y="205">4</text><text x="40" y="300">5</text><text x="100" y="366">6</text>
                  <text x="200" y="286">7</text><text x="300" y="366">8</text><text x="362" y="300">9</text>
                  <text x="284" y="205">10</text><text x="362" y="105">11</text><text x="300" y="40">12</text>
                </g>
                <g textAnchor="middle">
                  <text className="pl lagna" x="200" y="122"><tspan className="pgly">▲</tspan> As</text>
                  <text className="pl" x="105" y="74"><tspan className="pgly">♃</tspan> Ju</text>
                  <text className="pl" x="150" y="190"><tspan className="pgly">☽</tspan> Mo</text>
                  <text className="pl" x="82" y="205"><tspan className="pgly">☿</tspan> Me</text>
                  <text className="pl" x="102" y="330"><tspan className="pgly">☋</tspan> Ke</text>
                  <text className="pl" x="200" y="248"><tspan className="pgly">♂</tspan> Ma</text>
                  <text className="pl" x="326" y="292"><tspan className="pgly">☉</tspan> Su</text>
                  <text className="pl" x="326" y="318"><tspan className="pgly">♀</tspan> Ve</text>
                  <text className="pl" x="284" y="190"><tspan className="pgly">♄</tspan> Sa</text>
                  <text className="pl" x="300" y="330"><tspan className="pgly">☊</tspan> Ra</text>
                </g>
              </svg>

              {/* South Indian (fixed-sign grid) chart — same horoscope */}
              <svg className="vchart chart-south" viewBox="0 0 400 400" role="img" aria-label="A South Indian style Vedic birth chart">
                <rect className="frame" x="2" y="2" width="396" height="396" rx="6" />
                <rect className="grid" x="100" y="100" width="200" height="200" />
                <path className="grid" d="M100 2 L100 100 M200 2 L200 100 M300 2 L300 100 M100 300 L100 398 M200 300 L200 398 M300 300 L300 398 M2 100 L100 100 M2 200 L100 200 M2 300 L100 300 M300 100 L398 100 M300 200 L398 200 M300 300 L398 300" />
                <path className="lagna-mark" d="M100 36 L136 2" />
                <g className="sno" textAnchor="middle">
                  <text x="20" y="24">♓</text><text x="120" y="24">♈</text><text x="220" y="24">♉</text><text x="320" y="24">♊</text>
                  <text x="320" y="124">♋</text><text x="320" y="224">♌</text><text x="320" y="324">♍</text>
                  <text x="220" y="324">♎</text><text x="120" y="324">♏</text><text x="20" y="324">♐</text>
                  <text x="20" y="224">♑</text><text x="20" y="124">♒</text>
                </g>
                <g textAnchor="middle">
                  <text className="pl lagna" x="150" y="62"><tspan className="pgly">▲</tspan> As</text>
                  <text className="pl" x="250" y="62"><tspan className="pgly">♃</tspan> Ju</text>
                  <text className="pl" x="50" y="62"><tspan className="pgly">☊</tspan> Ra</text>
                  <text className="pl" x="350" y="146"><tspan className="pgly">☽</tspan> Mo</text>
                  <text className="pl" x="350" y="170"><tspan className="pgly">☿</tspan> Me</text>
                  <text className="pl" x="350" y="360"><tspan className="pgly">☋</tspan> Ke</text>
                  <text className="pl" x="250" y="360"><tspan className="pgly">♂</tspan> Ma</text>
                  <text className="pl" x="50" y="262"><tspan className="pgly">♄</tspan> Sa</text>
                  <text className="pl" x="50" y="346"><tspan className="pgly">☉</tspan> Su</text>
                  <text className="pl" x="50" y="370"><tspan className="pgly">♀</tspan> Ve</text>
                </g>
              </svg>

              <div className="chart-caption cap-north">North Indian · <b>Rasi</b></div>
              <div className="chart-caption cap-south">South Indian · <b>Rasi</b></div>
            </div>
          </div>
        </div>
      </header>

      {/* ===================== TRUST ===================== */}
      <section className="trust">
        <div className="wrap trust-inner">
          <span className="trust-item"><span className="dia" />Swiss Ephemeris precision</span>
          <span className="trust-item"><span className="dia" />27 nakshatras &amp; 16 vargas</span>
          <span className="trust-item"><span className="dia" />Vimsottari &amp; 40+ dashas</span>
          <span className="trust-item"><span className="dia" />KP · Jaimini · Tajaka</span>
          <span className="trust-item"><span className="dia" />Open-source engine</span>
        </div>
      </section>

      {/* ===================== FEATURES ===================== */}
      <section className="section" id="features">
        <div className="wrap">
          <div className="section-head reveal">
            <span className="eyebrow">Everything, in one sky</span>
            <h2>A full Jyotish practice, quietly doing the math for you.</h2>
            <p>Start with the essentials and go as deep as you like. The computation is exact; the explanation is human.</p>
          </div>
          <div className="feat-grid">
            {FEATURES.map((f) => (
              <article className="feat reveal" key={f.title}>
                <div className="feat-ic">{f.icon}</div>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
                <span className="tag">{f.tag}</span>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ===================== HOW IT WORKS ===================== */}
      <section className="section steps" id="how">
        <div className="wrap">
          <div className="section-head reveal">
            <span className="eyebrow">Three steps to your first reading</span>
            <h2>From birth details to real understanding, in a minute.</h2>
          </div>
          <div className="steps-grid">
            <div className="step reveal">
              <h3>Add your birth details</h3>
              <p>Date, time and place. Don&apos;t know your exact time? Rectify it from the events you do remember.</p>
            </div>
            <div className="step reveal">
              <h3>Get precise charts instantly</h3>
              <p>Every varga, dasha and strength measure is computed the moment you land — no waiting, no guesswork.</p>
            </div>
            <div className="step reveal">
              <h3>Ask, and understand</h3>
              <p>Chat in plain language or go deep into the classical detail. Toggle “explain simply” whenever you like.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ===================== AI DIFFERENTIATOR ===================== */}
      <section className="section" id="reading">
        <div className="wrap">
          <div className="ai-grid">
            <div className="ai-copy reveal">
              <span className="eyebrow">The difference</span>
              <h2>Answers you can trace back.</h2>
              <p>Most astrology apps hand you a confident paragraph and hope you believe it. {SITE_TITLE} shows its work.</p>
              <ul className="ai-points">
                <li><span className="chk">✓</span><span>Every reading is grounded in <strong>your actual computed positions</strong> — not a generic sun-sign.</span></li>
                <li><span className="chk">✓</span><span>Claims are <strong>cited to the classical texts</strong> they draw from, so you can read the source yourself.</span></li>
                <li><span className="chk">✓</span><span>When the tradition is silent, it <strong>says so</strong> instead of inventing a verdict.</span></li>
                <li><span className="chk">✓</span><span>One tap toggles between <strong>plain language and full technical depth</strong>.</span></li>
              </ul>
            </div>
            <div className="reading reveal">
              <div className="reading-top">
                <span className="dot dot-red" />
                <span className="dot dot-amber" />
                <span className="dot dot-green" />
                <span className="rlabel">ask · your chart</span>
              </div>
              <div className="reading-body">
                <div className="reading-q">When does my career finally settle down?</div>
                <p className="reading-a">
                  Your tenth house is ruled by Saturn, which turns strong in its own sign during the{" "}
                  <strong>Saturn–Mercury period beginning late 2027</strong>. Classical timing links this
                  pairing to steady, earned advancement rather than sudden change
                  <span className="cite" title="Brihat Parasara Hora Sastra, ch. 47">¹</span>. Transit Jupiter
                  reinforces it by crossing your tenth in the same window
                  <span className="cite" title="Phaladeepika, ch. 26">²</span>.
                </p>
                <div className="reading-src">
                  <span className="dia" style={{ width: 7, height: 7, transform: "rotate(45deg)", background: "var(--accent)", display: "inline-block" }} />
                  Sources: BPHS ch.47 · Phaladeepika ch.26
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===================== DEPTH / PRACTITIONER ===================== */}
      <section className="section depth" id="depth">
        <div className="wrap reveal">
          <span className="eyebrow">For serious practice, too</span>
          <h2>A friendly front door — with a full workbench behind it.</h2>
          <p>The same product a curious beginner opens is the one a working astrologer relies on. Nothing is dumbed down; the depth is simply one tap away.</p>
          <div className="chips">
            {DEPTH_CHIPS.map((c) => <span className="chip" key={c}>{c}</span>)}
          </div>
        </div>
      </section>

      {/* ===================== PRICING ===================== */}
      {SHOW_PRICING && (
        <section className="section" id="pricing">
          <div className="wrap">
            <div className="section-head center reveal">
              <span className="eyebrow">Simple, honest pricing</span>
              <h2>Start free. Upgrade when the sky gets interesting.</h2>
              <div className="price-toggle">
                <span className={`switch-label${!annual ? " on" : ""}`}>Monthly</span>
                <button
                  type="button"
                  className="switch"
                  role="switch"
                  aria-checked={annual}
                  aria-label="Toggle annual billing"
                  onClick={() => setAnnual((v) => !v)}
                >
                  <span className="knob" />
                </button>
                <span className={`switch-label${annual ? " on" : ""}`}>Annual</span>
                <span className="save-badge">Save ~20%</span>
              </div>
            </div>

            <div className="plans">
              {PLANS.map((plan) => (
                <div className={`plan reveal${plan.featured ? " featured" : ""}`} key={plan.name}>
                  {plan.flag && <span className="plan-flag">{plan.flag}</span>}
                  <div className="plan-name">{plan.name}</div>
                  <div className="plan-desc">{plan.desc}</div>
                  <div className="plan-price">
                    <span className="amt">{priceOf(plan)}</span>
                    <span className="per">{perOf(plan)}</span>
                  </div>
                  <div className="plan-annual-note">{annual && plan.annualNote ? plan.annualNote : " "}</div>
                  <ul>
                    {plan.features.map((feat) => (
                      <li key={feat}><span className="tick">◆</span>{feat}</li>
                    ))}
                  </ul>
                  <Link className={`btn ${plan.ctaClass}`} to="/register">{plan.cta}</Link>
                </div>
              ))}
            </div>
            <p className="price-note">Suggested pricing — final numbers are set in code; the whole section hides behind the REACT_APP_SHOW_PRICING flag.</p>
          </div>
        </section>
      )}

      {/* ===================== PRIVACY ===================== */}
      <section className="section" id="privacy">
        <div className="wrap">
          <div className="privacy-card reveal">
            <div>
              <span className="eyebrow">Your sky, your data</span>
              <h2>Your chart is yours.</h2>
              <p>Birth data is intimate. {SITE_TITLE} keeps it private by default, and you stay in control of every reading and conversation.</p>
            </div>
            <div className="privacy-list">
              <div><span className="d" />Private by default — export or delete anything, anytime.</div>
              <div><span className="d" />Built on the open-source PyJHora engine, self-hostable if you prefer.</div>
              <div><span className="d" />Your readings are never used to train anyone else&apos;s model.</div>
            </div>
          </div>
        </div>
      </section>

      {/* ===================== FINAL CTA ===================== */}
      <section className="final">
        <canvas className="stars2" ref={finalCanvas} />
        <div className="wrap">
          <span className="eyebrow" style={{ color: "var(--hero-gold)" }}>Jyotisha awaits</span>
          <h2 style={{ marginTop: 16 }}>The sky has been <span className="accent">waiting for you.</span></h2>
          <p>Add your birth details and get your first cited reading in under a minute. No card required.</p>
          <div className="hero-cta">
            <Link className="btn btn-primary" to="/register">Get started free</Link>
            <Link className="btn btn-ghost" to="/login">Log in</Link>
          </div>
        </div>
      </section>

      {/* ===================== FOOTER ===================== */}
      <footer className="footer">
        <div className="wrap">
          <div className="footer-grid">
            <div>
              <a className="brand" href="#top">
                <BrandMark />
                {SITE_TITLE}
              </a>
              <p className="footer-blurb">Ancient Jyotish, computed precisely and explained in plain language.</p>
            </div>
            <div className="footer-col">
              <h4>Product</h4>
              <a href="#features">Features</a>
              {SHOW_PRICING && <a href="#pricing">Pricing</a>}
              <a href="#depth">For practitioners</a>
              <Link to="/login">Log in</Link>
            </div>
            <div className="footer-col">
              <h4>Learn</h4>
              <a href="#features">Nakshatras</a><a href="#how">Dashas &amp; timing</a>
              <a href="#reading">The chart, explained</a><a href="#depth">Glossary</a>
            </div>
            <div className="footer-col">
              <h4>Company</h4>
              <a href="#privacy">Privacy</a>
              <Link to="/register">Get started</Link>
              <Link to="/login">Sign in</Link>
              <a href="#top">Back to top</a>
            </div>
          </div>
          <div className="footer-bottom">
            <small>© {new Date().getFullYear()} {SITE_TITLE}. All rights reserved.</small>
            <span className="disclaimer">For guidance and reflection — not a substitute for medical, legal, or financial advice.</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
