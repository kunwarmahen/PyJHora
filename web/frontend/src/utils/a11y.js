/**
 * Make a non-button behave like one (§68.8).
 *
 * The app has a number of controls that cannot be a `<button>` because they wrap
 * block content — a reading in the history list, a dasha node's header row.
 * `<button>` may not contain a `<div>`, so those stayed `<div onClick>`: no tab
 * stop, no announced role, nothing for Enter or Space. That is a keyboard user
 * locked out of opening a saved reading.
 *
 * Spread the result onto the element and it gains the whole button contract:
 *
 *   <div className="history-item" {...clickable(() => open(c), { label: c.title })}>
 *
 * Prefer a real `<button>` wherever the content allows one; this is for where it
 * does not.
 */
export const clickable = (onActivate, { label, expanded, disabled } = {}) => {
  if (disabled || typeof onActivate !== "function") return {};
  return {
    role: "button",
    tabIndex: 0,
    "aria-label": label,
    "aria-expanded": expanded,
    onClick: onActivate,
    onKeyDown: (e) => {
      // Space scrolls the page by default; Enter submits. A button does neither.
      if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
        e.preventDefault();
        onActivate(e);
      }
    },
  };
};

export default clickable;
