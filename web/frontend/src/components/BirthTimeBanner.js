import React from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AlertTriangle } from "lucide-react";
import "../styles/BirthTimeBanner.css";

/**
 * Honest-uncertainty banner for charts cast from an unreliable birth time.
 * Renders nothing when the time is exact. For "unknown" it warns that Lagna /
 * house / varga results are unreliable and to read Moon-referenced; for
 * "approximate" it softly cautions and links to rectification.
 */
export const BirthTimeBanner = ({ accuracy }) => {
  const { t } = useTranslation();
  const acc = (accuracy || "exact").toLowerCase();
  if (acc !== "unknown" && acc !== "approximate") return null;

  return (
    <div className={`btb btb--${acc}`}>
      <AlertTriangle size={18} className="btb__icon" />
      <div className="btb__body">
        <strong>{t(`birthTime.${acc}Title`)}</strong>
        <span> {t(`birthTime.${acc}Body`)}</span>{" "}
        <Link to="/rectify" className="btb__link">
          {t("birthTime.rectifyLink")}
        </Link>
      </div>
    </div>
  );
};

export default BirthTimeBanner;
