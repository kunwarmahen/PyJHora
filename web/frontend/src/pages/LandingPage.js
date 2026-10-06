import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";
import { Sun, Moon, Monitor, Languages } from "lucide-react";
import { useSettings } from "../contexts/SettingsContext";
import { resolveTheme } from "../config/theme";
import { SITE_TITLE } from "../config/branding";
import "../styles/Landing.css";
import { PreviewForm } from "../components/PreviewForm";
import { onboardingService } from "../services/api";

/* Pricing shows only when REACT_APP_SHOW_PRICING === "true" (see .env). */
const SHOW_PRICING = process.env.REACT_APP_SHOW_PRICING === "true";

const THEME_ORDER = ["light", "dark", "system"];
const THEME_ICON = { light: Sun, dark: Moon, system: Monitor };

const BrandMark = () => (
  <svg className="brand-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <rect x="3" y="3" width="34" height="34" rx="3" className="stroke" strokeWidth="2" />
    <path d="M20 3 L37 20 L20 37 L3 20 Z" className="stroke" strokeWidth="1.6" />
    <path d="M3 3 L37 37 M37 3 L3 37" className="stroke" strokeWidth="1.2" opacity="0.7" />
  </svg>
);

// Text lives in the locale files (landing.pricing.plans.<id>); prices stay here.
const PLANS = [
  { id: "free", price: "$0", ctaClass: "btn-outline" },
  { id: "pro", featured: true, monthly: "$9", annual: "$7", ctaClass: "btn-primary" },
  { id: "practitioner", monthly: "$29", annual: "$23", ctaClass: "btn-outline" },
];

// Text: landing.features.items.<key>.
const FEATURES = [
  {
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      >
        <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
        <circle cx="12" cy="12" r="4" />
      </svg>
    ),
    key: "readings",
  },
  {
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <rect x="4" y="4" width="16" height="16" rx="2" />
        <path d="M4 4 20 20M20 4 4 20" />
      </svg>
    ),
    key: "charts",
  },
  {
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      >
        <path d="M12 6v6l4 2" />
        <circle cx="12" cy="12" r="9" />
      </svg>
    ),
    key: "timing",
  },
  {
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      >
        <circle cx="8" cy="9" r="3.5" />
        <circle cx="16" cy="9" r="3.5" />
        <path d="M4 20c0-3 2-5 4-5s4 2 4 5M12 20c0-3 2-5 4-5s4 2 4 5" />
      </svg>
    ),
    key: "compat",
  },
  {
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      >
        <path
          d="M12 2 15 9l7 .5-5.5 4.5L20 21l-8-4.5L4 21l1.5-7L0 9.5 7 9z"
          transform="scale(0.9) translate(1.2 1.2)"
        />
      </svg>
    ),
    key: "systems",
  },
  {
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      >
        <path d="M12 3a9 9 0 1 0 9 9M12 3v9l6-4" />
      </svg>
    ),
    key: "daily",
  },
];

/** Slow, tilted spiral galaxy tucked into the hero's top-right corner + starfield. */
function makeStarfield(canvas, count, opts, reduce) {
  if (!canvas) return () => {};
  opts = opts || {};
  const ctx = canvas.getContext("2d");
  let stars = [],
    planets = [],
    gal = [],
    gx,
    gy,
    gR,
    w,
    h,
    dpr,
    raf;
  let t = 0;
  const tilt = -0.5,
    ct = Math.cos(tilt),
    st = Math.sin(tilt);

  function size() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = canvas.clientWidth;
    h = canvas.clientHeight;
    if (!w || !h) return;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    stars = [];
    for (let i = 0; i < count; i++) {
      stars.push({
        x: Math.random() * w,
        y: Math.random() * h,
        r: Math.random() * 1.3 + 0.2,
        a: Math.random() * 0.6 + 0.2,
        tw: Math.random() * 0.02 + 0.004,
        ph: Math.random() * 6.28,
      });
    }
    if (opts.planets) {
      planets = [];
      const cols = ["#ff9f3d", "#ffc266", "#ff6a4d", "#9db8ff", "#ffe0a3"];
      for (let j = 0; j < 5; j++) {
        planets.push({
          x: (0.12 + j * 0.19) * w,
          y: (0.2 + Math.sin(j) * 0.12) * h + h * 0.15,
          r: Math.random() * 1.6 + 1.6,
          c: cols[j],
        });
      }
    }
    if (opts.galaxy) {
      gx = w * 0.9;
      gy = h * 0.15;
      gR = Math.max(70, Math.min(w, h) * 0.17);
      gal = [];
      const N = 150,
        turns = 2.6;
      for (let k = 0; k < N; k++) {
        const frac = k / N,
          arm = k % 2;
        const theta = frac * turns * 6.283 + arm * Math.PI;
        const jit = (Math.random() - 0.5) * 0.5;
        const col = frac < 0.28 ? "#ffd9a0" : frac < 0.6 ? "#f6ecd8" : "#9fb6ff";
        gal.push({
          th: theta + jit,
          rad: frac * gR,
          sz: Math.random() * 1.1 + 0.5,
          c: col,
          a: (1 - frac) * 0.85 + 0.1,
          tw: Math.random() * 0.02 + 0.006,
          ph: Math.random() * 6.28,
        });
      }
    }
  }

  function drawGalaxy() {
    const core = ctx.createRadialGradient(gx, gy, 0, gx, gy, gR * 0.7);
    core.addColorStop(0, "rgba(255,210,150,0.55)");
    core.addColorStop(0.4, "rgba(255,170,90,0.16)");
    core.addColorStop(1, "transparent");
    ctx.globalAlpha = 1;
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(gx, gy, gR * 0.9, 0, 6.283);
    ctx.fill();
    const rot = t * 0.0011;
    for (let k = 0; k < gal.length; k++) {
      const p = gal[k],
        ang = p.th + rot;
      const px = Math.cos(ang) * p.rad,
        py = Math.sin(ang) * p.rad * 0.5;
      const x = gx + px * ct - py * st,
        y = gy + px * st + py * ct;
      ctx.globalAlpha = Math.max(0.05, p.a + Math.sin(t * p.tw * 60 + p.ph) * 0.2);
      ctx.beginPath();
      ctx.arc(x, y, p.sz, 0, 6.283);
      ctx.fillStyle = p.c;
      ctx.fill();
    }
    ctx.globalAlpha = 0.95;
    ctx.fillStyle = "#fff3dd";
    ctx.beginPath();
    ctx.arc(gx, gy, 2.4, 0, 6.283);
    ctx.fill();
  }

  function draw() {
    if (!w || !h) {
      raf = requestAnimationFrame(draw);
      return;
    }
    ctx.clearRect(0, 0, w, h);
    if (opts.galaxy) drawGalaxy();
    for (let i = 0; i < stars.length; i++) {
      const s = stars[i];
      const a = s.a + Math.sin(t * s.tw * 60 + s.ph) * 0.25;
      ctx.globalAlpha = Math.max(0.05, Math.min(1, a));
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, 6.283);
      ctx.fillStyle = "#f4ecdb";
      ctx.fill();
    }
    if (opts.planets) {
      for (let j = 0; j < planets.length; j++) {
        const p = planets[j];
        ctx.globalAlpha = 0.9;
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4);
        g.addColorStop(0, p.c);
        g.addColorStop(1, "transparent");
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * 4, 0, 6.283);
        ctx.fillStyle = g;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, 6.283);
        ctx.fillStyle = p.c;
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
    t += 1;
    if (!reduce) raf = requestAnimationFrame(draw);
  }

  function onResize() {
    cancelAnimationFrame(raf);
    size();
    draw();
  }
  size();
  draw();
  window.addEventListener("resize", onResize);
  return () => {
    cancelAnimationFrame(raf);
    window.removeEventListener("resize", onResize);
  };
}

export const LandingPage = () => {
  const { settings, updateSetting } = useSettings();
  const { t, i18n } = useTranslation();
  // Landing copy exists in en + hi only, so the button offers the other one of
  // those two (§83.6); a Sanskrit reader sees English copy and can pick Hindi.
  const lang = (i18n.language || "en").split("-")[0];
  const otherLang =
    lang === "hi" ? { code: "en", native: "English" } : { code: "hi", native: "हिन्दी" };
  const themeName = (k) => t(`landing.theme.${k}`);
  const [scrolled, setScrolled] = useState(false);
  const [annual, setAnnual] = useState(false);
  const rootRef = useRef(null);
  const heroCanvas = useRef(null);
  const finalCanvas = useRef(null);

  const pref = settings.theme || "system";
  const ThemeIcon = THEME_ICON[pref] || Monitor;
  const nextTheme = THEME_ORDER[(THEME_ORDER.indexOf(pref) + 1) % THEME_ORDER.length];
  const themeLabel =
    pref === "system"
      ? `${themeName("system")} · ${themeName(resolveTheme("system") === "dark" ? "dark" : "light")}`
      : themeName(pref);

  // Funnel step one (§76.8): the landing page was opened. Counts only.
  useEffect(() => {
    // Fire-and-forget: a counter must never surface as an error on the page.
    Promise.resolve(onboardingService.beacon("landing_view")).catch(() => {});
  }, []);

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
      io = new IntersectionObserver(
        (entries) => {
          entries.forEach((e) => {
            if (e.isIntersecting) {
              e.target.classList.add("in");
              io.unobserve(e.target);
            }
          });
        },
        { threshold: 0.14 }
      );
      revealEls.forEach((el) => io.observe(el));
    }

    // Starfields
    const disposeHero = makeStarfield(
      heroCanvas.current,
      150,
      { planets: true, galaxy: true },
      reduce
    );
    const disposeFinal = makeStarfield(finalCanvas.current, 90, {}, reduce);

    return () => {
      window.removeEventListener("scroll", onScroll);
      if (io) io.disconnect();
      disposeHero();
      disposeFinal();
    };
  }, []);

  const priceOf = (plan) => (plan.price ? plan.price : annual ? plan.annual : plan.monthly);
  const perOf = (plan) =>
    plan.price
      ? t(`landing.pricing.plans.${plan.id}.per`)
      : t(annual ? "landing.pricing.perMonthYearly" : "landing.pricing.perMonth");
  const list = (key) => {
    const v = t(key, { returnObjects: true });
    return Array.isArray(v) ? v : [];
  };

  return (
    <div className="landing" ref={rootRef}>
      {/* ===================== NAV ===================== */}
      <nav className={`nav${scrolled ? " scrolled" : ""}`}>
        <div className="nav-inner">
          <a
            className="brand"
            href="#top"
            aria-label={t("landing.nav.homeAria", { site: SITE_TITLE })}
          >
            <BrandMark />
            {SITE_TITLE}
          </a>
          <div className="nav-links">
            <a href="#features">{t("landing.nav.features")}</a>
            <a href="#how">{t("landing.nav.how")}</a>
            <a href="#depth">{t("landing.nav.depth")}</a>
            {SHOW_PRICING && <a href="#pricing">{t("landing.nav.pricing")}</a>}
          </div>
          <div className="nav-right">
            <button
              type="button"
              className="theme-toggle"
              onClick={() => updateSetting("theme", nextTheme)}
              title={t("landing.theme.switchTitle", { next: themeName(nextTheme) })}
              aria-label={t("landing.theme.switchAria", { current: themeLabel })}
            >
              <ThemeIcon size={16} />
              <span className="tt-label">{themeLabel}</span>
            </button>
            <button
              type="button"
              className="theme-toggle"
              lang={otherLang.code}
              onClick={() => updateSetting("language", otherLang.code)}
              aria-label={t("landing.lang.switchAria", { language: otherLang.native })}
            >
              <Languages size={16} />
              <span className="tt-label">{otherLang.native}</span>
            </button>
            <Link className="login-link" to="/login">
              {t("landing.nav.login")}
            </Link>
            <Link className="btn btn-primary" to="/register">
              {t("landing.nav.getStarted")}
            </Link>
          </div>
        </div>
      </nav>

      {/* ===================== HERO ===================== */}
      <header className="hero" id="top">
        <canvas className="stars" ref={heroCanvas} />
        <div className="wrap">
          <div className="hero-grid">
            <div className="hero-copy">
              <span className="eyebrow">{t("landing.hero.eyebrow")}</span>
              <h1>
                <Trans
                  i18nKey="landing.hero.title"
                  components={{ accent: <span className="accent" /> }}
                />
              </h1>
              <p className="hero-sub">{t("landing.hero.sub", { site: SITE_TITLE })}</p>
              <div className="hero-cta">
                <Link className="btn btn-primary" to="/register">
                  {t("landing.nav.getStarted")}
                </Link>
                <a className="btn btn-ghost" href="#try">
                  {t("landing.hero.seeFree")}
                </a>
              </div>
              <div className="hero-meta">
                {list("landing.hero.meta").map((m) => (
                  <span key={m}>{m}</span>
                ))}
              </div>
            </div>

            <div className="chart-stage">
              <div className="chart-halo" />
              {/* North Indian (diamond) chart signature */}
              <svg
                className="vchart chart-north"
                viewBox="0 0 400 400"
                role="img"
                aria-label={t("landing.chart.northAria")}
              >
                <rect className="frame" x="2" y="2" width="396" height="396" rx="6" />
                <path className="grid" d="M2 2 L398 398 M398 2 L2 398" />
                <path className="grid" d="M200 2 L398 200 L200 398 L2 200 Z" />
                <g className="hno" textAnchor="middle">
                  <text x="200" y="66">
                    1
                  </text>
                  <text x="100" y="40">
                    2
                  </text>
                  <text x="40" y="105">
                    3
                  </text>
                  <text x="116" y="205">
                    4
                  </text>
                  <text x="40" y="300">
                    5
                  </text>
                  <text x="100" y="366">
                    6
                  </text>
                  <text x="200" y="286">
                    7
                  </text>
                  <text x="300" y="366">
                    8
                  </text>
                  <text x="362" y="300">
                    9
                  </text>
                  <text x="284" y="205">
                    10
                  </text>
                  <text x="362" y="105">
                    11
                  </text>
                  <text x="300" y="40">
                    12
                  </text>
                </g>
                <g textAnchor="middle">
                  <text className="pl lagna" x="200" y="122">
                    <tspan className="pgly">▲</tspan> As
                  </text>
                  <text className="pl" x="105" y="74">
                    <tspan className="pgly">♃</tspan> Ju
                  </text>
                  <text className="pl" x="150" y="190">
                    <tspan className="pgly">☽</tspan> Mo
                  </text>
                  <text className="pl" x="82" y="205">
                    <tspan className="pgly">☿</tspan> Me
                  </text>
                  <text className="pl" x="102" y="330">
                    <tspan className="pgly">☋</tspan> Ke
                  </text>
                  <text className="pl" x="200" y="248">
                    <tspan className="pgly">♂</tspan> Ma
                  </text>
                  <text className="pl" x="326" y="292">
                    <tspan className="pgly">☉</tspan> Su
                  </text>
                  <text className="pl" x="326" y="318">
                    <tspan className="pgly">♀</tspan> Ve
                  </text>
                  <text className="pl" x="284" y="190">
                    <tspan className="pgly">♄</tspan> Sa
                  </text>
                  <text className="pl" x="300" y="330">
                    <tspan className="pgly">☊</tspan> Ra
                  </text>
                </g>
              </svg>

              {/* South Indian (fixed-sign grid) chart — same horoscope */}
              <svg
                className="vchart chart-south"
                viewBox="0 0 400 400"
                role="img"
                aria-label={t("landing.chart.southAria")}
              >
                <rect className="frame" x="2" y="2" width="396" height="396" rx="6" />
                <rect className="grid" x="100" y="100" width="200" height="200" />
                <path
                  className="grid"
                  d="M100 2 L100 100 M200 2 L200 100 M300 2 L300 100 M100 300 L100 398 M200 300 L200 398 M300 300 L300 398 M2 100 L100 100 M2 200 L100 200 M2 300 L100 300 M300 100 L398 100 M300 200 L398 200 M300 300 L398 300"
                />
                <path className="lagna-mark" d="M100 36 L136 2" />
                <g className="sno" textAnchor="middle">
                  <text x="20" y="24">
                    ♓
                  </text>
                  <text x="120" y="24">
                    ♈
                  </text>
                  <text x="220" y="24">
                    ♉
                  </text>
                  <text x="320" y="24">
                    ♊
                  </text>
                  <text x="320" y="124">
                    ♋
                  </text>
                  <text x="320" y="224">
                    ♌
                  </text>
                  <text x="320" y="324">
                    ♍
                  </text>
                  <text x="220" y="324">
                    ♎
                  </text>
                  <text x="120" y="324">
                    ♏
                  </text>
                  <text x="20" y="324">
                    ♐
                  </text>
                  <text x="20" y="224">
                    ♑
                  </text>
                  <text x="20" y="124">
                    ♒
                  </text>
                </g>
                <g textAnchor="middle">
                  <text className="pl lagna" x="150" y="62">
                    <tspan className="pgly">▲</tspan> As
                  </text>
                  <text className="pl" x="250" y="62">
                    <tspan className="pgly">♃</tspan> Ju
                  </text>
                  <text className="pl" x="50" y="62">
                    <tspan className="pgly">☊</tspan> Ra
                  </text>
                  <text className="pl" x="350" y="146">
                    <tspan className="pgly">☽</tspan> Mo
                  </text>
                  <text className="pl" x="350" y="170">
                    <tspan className="pgly">☿</tspan> Me
                  </text>
                  <text className="pl" x="350" y="360">
                    <tspan className="pgly">☋</tspan> Ke
                  </text>
                  <text className="pl" x="250" y="360">
                    <tspan className="pgly">♂</tspan> Ma
                  </text>
                  <text className="pl" x="50" y="262">
                    <tspan className="pgly">♄</tspan> Sa
                  </text>
                  <text className="pl" x="50" y="346">
                    <tspan className="pgly">☉</tspan> Su
                  </text>
                  <text className="pl" x="50" y="370">
                    <tspan className="pgly">♀</tspan> Ve
                  </text>
                </g>
              </svg>

              <div className="chart-caption cap-north">
                <Trans i18nKey="landing.chart.northCap" components={{ b: <b /> }} />
              </div>
              <div className="chart-caption cap-south">
                <Trans i18nKey="landing.chart.southCap" components={{ b: <b /> }} />
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* ===================== TRUST ===================== */}
      <section className="trust">
        <div className="wrap trust-inner">
          {list("landing.trust").map((item) => (
            <span className="trust-item" key={item}>
              <span className="dia" />
              {item}
            </span>
          ))}
        </div>
      </section>

      {/* ===================== TRY IT (§76.7) ===================== */}
      <section className="section" id="try">
        <div className="wrap">
          <div className="section-head reveal in">
            <span className="eyebrow">{t("landing.try.eyebrow")}</span>
            <h2>{t("landing.try.title")}</h2>
            <p>{t("landing.try.body")}</p>
          </div>
          <PreviewForm />
        </div>
      </section>

      {/* ===================== FEATURES ===================== */}
      <section className="section" id="features">
        <div className="wrap">
          <div className="section-head reveal">
            <span className="eyebrow">{t("landing.features.eyebrow")}</span>
            <h2>{t("landing.features.title")}</h2>
            <p>{t("landing.features.body")}</p>
          </div>
          <div className="feat-grid">
            {FEATURES.map((f) => (
              <article className="feat reveal" key={f.key}>
                <div className="feat-ic">{f.icon}</div>
                <h3>{t(`landing.features.items.${f.key}.title`)}</h3>
                <p>{t(`landing.features.items.${f.key}.body`)}</p>
                <span className="tag">{t(`landing.features.items.${f.key}.tag`)}</span>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ===================== HOW IT WORKS ===================== */}
      <section className="section steps" id="how">
        <div className="wrap">
          <div className="section-head reveal">
            <span className="eyebrow">{t("landing.how.eyebrow")}</span>
            <h2>{t("landing.how.title")}</h2>
          </div>
          <div className="steps-grid">
            {list("landing.how.steps").map((step) => (
              <div className="step reveal" key={step.title}>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===================== AI DIFFERENTIATOR ===================== */}
      <section className="section" id="reading">
        <div className="wrap">
          <div className="ai-grid">
            <div className="ai-copy reveal">
              <span className="eyebrow">{t("landing.ai.eyebrow")}</span>
              <h2>{t("landing.ai.title")}</h2>
              <p>{t("landing.ai.intro", { site: SITE_TITLE })}</p>
              <ul className="ai-points">
                {list("landing.ai.points").map((_, i) => (
                  <li key={i}>
                    <span className="chk">✓</span>
                    <span>
                      <Trans i18nKey={`landing.ai.points.${i}`} />
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="reading reveal">
              <div className="reading-top">
                <span className="dot dot-red" />
                <span className="dot dot-amber" />
                <span className="dot dot-green" />
                <span className="rlabel">{t("landing.ai.demo.label")}</span>
              </div>
              <div className="reading-body">
                <div className="reading-q">{t("landing.ai.demo.q")}</div>
                <p className="reading-a">
                  <Trans
                    i18nKey="landing.ai.demo.a"
                    components={{
                      cite1: <span className="cite" title="Brihat Parasara Hora Sastra, ch. 47" />,
                      cite2: <span className="cite" title="Phaladeepika, ch. 26" />,
                    }}
                  />
                </p>
                <div className="reading-src">
                  <span
                    className="dia"
                    style={{
                      width: 7,
                      height: 7,
                      transform: "rotate(45deg)",
                      background: "var(--accent)",
                      display: "inline-block",
                    }}
                  />
                  {t("landing.ai.demo.sources")}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===================== DEPTH / PRACTITIONER ===================== */}
      <section className="section depth" id="depth">
        <div className="wrap reveal">
          <span className="eyebrow">{t("landing.depth.eyebrow")}</span>
          <h2>{t("landing.depth.title")}</h2>
          <p>{t("landing.depth.body")}</p>
          <div className="chips">
            {list("landing.depth.chips").map((c) => (
              <span className="chip" key={c}>
                {c}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ===================== PRICING ===================== */}
      {SHOW_PRICING && (
        <section className="section" id="pricing">
          <div className="wrap">
            <div className="section-head center reveal">
              <span className="eyebrow">{t("landing.pricing.eyebrow")}</span>
              <h2>{t("landing.pricing.title")}</h2>
              <div className="price-toggle">
                <span className={`switch-label${!annual ? " on" : ""}`}>
                  {t("landing.pricing.monthly")}
                </span>
                <button
                  type="button"
                  className="switch"
                  role="switch"
                  aria-checked={annual}
                  aria-label={t("landing.pricing.toggleAria")}
                  onClick={() => setAnnual((v) => !v)}
                >
                  <span className="knob" />
                </button>
                <span className={`switch-label${annual ? " on" : ""}`}>
                  {t("landing.pricing.annual")}
                </span>
                <span className="save-badge">{t("landing.pricing.save")}</span>
              </div>
            </div>

            <div className="plans">
              {PLANS.map((plan) => {
                const k = `landing.pricing.plans.${plan.id}`;
                return (
                  <div className={`plan reveal${plan.featured ? " featured" : ""}`} key={plan.id}>
                    {plan.featured && <span className="plan-flag">{t(`${k}.flag`)}</span>}
                    <div className="plan-name">{t(`${k}.name`)}</div>
                    <div className="plan-desc">{t(`${k}.desc`)}</div>
                    <div className="plan-price">
                      <span className="amt">{priceOf(plan)}</span>
                      <span className="per">{perOf(plan)}</span>
                    </div>
                    <div className="plan-annual-note">
                      {annual && plan.annual ? t(`${k}.annualNote`) : " "}
                    </div>
                    <ul>
                      {list(`${k}.features`).map((feat) => (
                        <li key={feat}>
                          <span className="tick">◆</span>
                          {feat}
                        </li>
                      ))}
                    </ul>
                    <Link className={`btn ${plan.ctaClass}`} to="/register">
                      {t(`${k}.cta`)}
                    </Link>
                  </div>
                );
              })}
            </div>
            <p className="price-note">{t("landing.pricing.note")}</p>
          </div>
        </section>
      )}

      {/* ===================== PRIVACY ===================== */}
      <section className="section" id="privacy">
        <div className="wrap">
          <div className="privacy-card reveal">
            <div>
              <span className="eyebrow">{t("landing.privacy.eyebrow")}</span>
              <h2>{t("landing.privacy.title")}</h2>
              <p>{t("landing.privacy.body", { site: SITE_TITLE })}</p>
            </div>
            <div className="privacy-list">
              {list("landing.privacy.items").map((item) => (
                <div key={item}>
                  <span className="d" />
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ===================== FINAL CTA ===================== */}
      <section className="final">
        <canvas className="stars2" ref={finalCanvas} />
        <div className="wrap">
          <span className="eyebrow" style={{ color: "var(--hero-gold)" }}>
            {t("landing.final.eyebrow")}
          </span>
          <h2 style={{ marginTop: 16 }}>
            <Trans
              i18nKey="landing.final.title"
              components={{ accent: <span className="accent" /> }}
            />
          </h2>
          <p>{t("landing.final.body")}</p>
          <div className="hero-cta">
            <Link className="btn btn-primary" to="/register">
              {t("landing.nav.getStarted")}
            </Link>
            <Link className="btn btn-ghost" to="/login">
              {t("landing.nav.login")}
            </Link>
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
              <p className="footer-blurb">{t("landing.footer.blurb")}</p>
            </div>
            <div className="footer-col">
              <h4>{t("landing.footer.product")}</h4>
              <a href="#features">{t("landing.nav.features")}</a>
              {SHOW_PRICING && <a href="#pricing">{t("landing.nav.pricing")}</a>}
              <a href="#depth">{t("landing.nav.depth")}</a>
              <Link to="/login">{t("landing.nav.login")}</Link>
            </div>
            <div className="footer-col">
              <h4>{t("landing.footer.learn")}</h4>
              <a href="#features">{t("landing.footer.nakshatras")}</a>
              <a href="#how">{t("landing.footer.dashas")}</a>
              <a href="#reading">{t("landing.footer.explained")}</a>
              <a href="#depth">{t("landing.footer.glossary")}</a>
            </div>
            <div className="footer-col">
              <h4>{t("landing.footer.company")}</h4>
              <a href="#privacy">{t("landing.footer.privacy")}</a>
              <Link to="/register">{t("landing.footer.getStarted")}</Link>
              <Link to="/login">{t("landing.footer.signIn")}</Link>
              <a href="#top">{t("landing.footer.top")}</a>
            </div>
          </div>
          <div className="footer-bottom">
            <small>
              {t("landing.footer.rights", { year: new Date().getFullYear(), site: SITE_TITLE })}
            </small>
            <span className="disclaimer">{t("landing.footer.disclaimer")}</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
