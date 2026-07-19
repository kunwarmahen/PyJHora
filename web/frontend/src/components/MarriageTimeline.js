import React, { useMemo } from "react";
import { useLocalizeName } from "../i18n/localizeName";

// A dual Vimsottari-Mahadasha overlap band for a couple (§2.6). Both partners'
// maha periods are laid on one shared calendar axis; periods ruled by a marriage
// significator (that partner's 7th lord, Venus or Jupiter) are highlighted as the
// windows when marriage themes activate.
const parse = (s) => {
  const [y, m, d] = (s || "").split("-").map(Number);
  return y ? new Date(y, (m || 1) - 1, d || 1).getTime() : NaN;
};

const PartnerBand = ({ name, periods, significant, domainStart, domainSpan }) => {
  const ln = useLocalizeName();
  return (
    <div className="mt-band">
      <div className="mt-band__name">{name}</div>
      <div className="mt-band__track">
        {periods.map((p, i) => {
          const s = parse(p.start_date);
          const e = parse(p.end_date);
          if (isNaN(s) || isNaN(e)) return null;
          const left = ((s - domainStart) / domainSpan) * 100;
          const width = ((e - s) / domainSpan) * 100;
          const isSig = significant.has(p.lord);
          return (
            <div
              key={i}
              className={`mt-seg ${isSig ? "mt-seg--sig" : ""}`}
              style={{ left: `${left}%`, width: `${width}%` }}
              title={`${p.lord}: ${p.start_date} → ${p.end_date}`}
            >
              <span className="mt-seg__label">{ln(p.lord, "graha", { abbr: true })}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const MarriageTimeline = ({ t, nameA, nameB, dashaA, dashaB, sigA, sigB }) => {
  const seqA = useMemo(() => dashaA?.dasha_sequence || [], [dashaA]);
  const seqB = useMemo(() => dashaB?.dasha_sequence || [], [dashaB]);

  const { domainStart, domainSpan, nowPct } = useMemo(() => {
    const all = [...seqA, ...seqB];
    const starts = all.map((p) => parse(p.start_date)).filter((n) => !isNaN(n));
    const ends = all.map((p) => parse(p.end_date)).filter((n) => !isNaN(n));
    if (!starts.length || !ends.length) {
      return { domainStart: 0, domainSpan: 1, nowPct: null };
    }
    const ds = Math.min(...starts);
    const de = Math.max(...ends);
    const span = de - ds || 1;
    const now = Date.now();
    const pct = now >= ds && now <= de ? ((now - ds) / span) * 100 : null;
    return { domainStart: ds, domainSpan: span, nowPct: pct };
  }, [seqA, seqB]);

  // Decade grid labels across the shared axis.
  const yearMarks = useMemo(() => {
    if (!domainSpan || domainSpan === 1) return [];
    const startYear = new Date(domainStart).getFullYear();
    const endYear = new Date(domainStart + domainSpan).getFullYear();
    const marks = [];
    for (let y = Math.ceil(startYear / 10) * 10; y <= endYear; y += 10) {
      const t0 = new Date(y, 0, 1).getTime();
      marks.push({ year: y, pct: ((t0 - domainStart) / domainSpan) * 100 });
    }
    return marks;
  }, [domainStart, domainSpan]);

  if (!seqA.length && !seqB.length) return null;

  return (
    <div className="mt-wrap">
      <div className="mt-axis">
        {yearMarks.map((m) => (
          <span key={m.year} className="mt-axis__mark" style={{ left: `${m.pct}%` }}>
            {m.year}
          </span>
        ))}
        {nowPct != null && (
          <span className="mt-now" style={{ left: `${nowPct}%` }} title={t("compat.timeline.now")}>
            <span className="mt-now__dot" />
          </span>
        )}
      </div>
      <PartnerBand
        name={nameA}
        periods={seqA}
        significant={sigA}
        domainStart={domainStart}
        domainSpan={domainSpan}
      />
      <PartnerBand
        name={nameB}
        periods={seqB}
        significant={sigB}
        domainStart={domainStart}
        domainSpan={domainSpan}
      />
      <div className="mt-legend">
        <span className="mt-legend__item">
          <span className="mt-swatch mt-swatch--sig" /> {t("compat.timeline.significant")}
        </span>
      </div>
    </div>
  );
};
