import React, { useState } from "react";
import { lookupGlossary } from "../constants/glossary";
import "../styles/Shared.css";

/**
 * Wraps a Sanskrit/Jyotish term with a definition tooltip. Hover (desktop) or
 * tap/focus (mobile) to reveal. If `term`/children isn't in the glossary it
 * renders the text plainly (no decoration), so it's always safe to use.
 *
 *   <GlossaryTerm>Lagna</GlossaryTerm>
 *   <GlossaryTerm term="Sarva">Sarva (SAV)</GlossaryTerm>
 */
export const GlossaryTerm = ({ term, children }) => {
  const [open, setOpen] = useState(false);
  const label = children ?? term;
  const def = lookupGlossary(term ?? (typeof children === "string" ? children : null));

  if (!def) return <>{label}</>;

  return (
    <span
      className="glossary-term"
      tabIndex={0}
      role="button"
      aria-label={`${typeof label === "string" ? label : term}: ${def}`}
      onClick={() => setOpen((o) => !o)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {label}
      <span className={`glossary-pop ${open ? "open" : ""}`} role="tooltip">
        {def}
      </span>
    </span>
  );
};

export default GlossaryTerm;
