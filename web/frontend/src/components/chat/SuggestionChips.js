import React from "react";

/**
 * A wrap-around row of tappable suggestion chips. Shared by the Ask Astrologer
 * page and the Transit chat for one-tap starter questions.
 */
export const SuggestionChips = ({ chips, onSelect, disabled }) => {
  if (!chips || chips.length === 0) return null;
  return (
    <div className="chat-chips">
      {chips.map((c) => (
        <button
          key={c}
          type="button"
          className="chat-chip"
          onClick={() => onSelect(c)}
          disabled={disabled}
        >
          {c}
        </button>
      ))}
    </div>
  );
};

export default SuggestionChips;
