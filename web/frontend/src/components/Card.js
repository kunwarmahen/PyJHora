import React from "react";
import "../styles/Shared.css";

/**
 * White content card with the saffron Vedic styling. Optional accent top-border
 * and an optional header (icon + title, plus a right-aligned `count`/`actions`).
 *
 * accent: "saffron" | "indigo" | "vermillion" | "gold" | null
 */
export const Card = ({
  title,
  icon,
  accent = "saffron",
  count,
  actions,
  className = "",
  style,
  children,
}) => {
  const accentClass =
    accent === "saffron" ? "ui-card--accent" : accent ? `ui-card--accent-${accent}` : "";
  return (
    <div className={`ui-card ${accentClass} ${className}`.trim()} style={style}>
      {(title || icon) && (
        <div className="ui-card-header">
          {icon}
          {title && <span>{title}</span>}
          {count != null && <span className="ui-card-count">{count}</span>}
          {actions}
        </div>
      )}
      {children}
    </div>
  );
};

export default Card;
