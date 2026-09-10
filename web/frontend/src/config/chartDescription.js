/**
 * What a kundali says out loud (§68.8).
 *
 * Both chart styles render as a grid of `<div>`s carrying `role="img"` and an
 * aria-label of just the title — so a screen reader announced "Rasi Chart,
 * image" and nothing else, and `role="img"` additionally hides every planet
 * inside from assistive technology. The chart, the single most important thing
 * in the app, was unreadable.
 *
 * A complex diagram is allowed a long text alternative, and that is what this
 * builds: the same facts the eye takes off the grid, in reading order. It stays
 * out of the components so both styles say the same thing in the same words,
 * and so it can be tested without mounting React (§68.3 — no page has ever been
 * rendered in a test).
 *
 * Kept deliberately literal. It describes placements; it does not interpret.
 */

/**
 * @param {object} opts
 * @param {string} opts.title      chart name, already translated
 * @param {string} opts.subtitle   style name, already translated
 * @param {Array}  opts.cells      in reading order: { label, items: [names] }
 *                                 `label` is the sign or house, already localized;
 *                                 `items` are occupant names, already localized.
 * @param {string} [opts.ascendant] where the Lagna sits, already localized
 * @param {function} opts.t        i18next `t`
 */
export const describeChart = ({ title, subtitle, cells = [], ascendant, t }) => {
  const head = subtitle ? `${title}, ${subtitle}.` : `${title}.`;
  const asc = ascendant ? ` ${t("chartA11y.ascendant", { place: ascendant })}` : "";
  const body = cells
    .map(({ label, items }) =>
      items && items.length
        ? t("chartA11y.cell", { place: label, occupants: items.join(", ") })
        : t("chartA11y.empty", { place: label })
    )
    .join(" ");
  return `${head}${asc} ${body}`.trim();
};

export default describeChart;
