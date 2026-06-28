import React from "react";
import "../styles/Shared.css";

/** A labelled value cell (label above, value below) used in detail grids.
 * Optional `icon` renders beside the label (saffron-tinted). */
export const DataField = ({ label, value, icon, children }) => (
  <div className="ui-datafield">
    <div className="ui-datafield-label">
      {icon}
      <span>{label}</span>
    </div>
    <div className="ui-datafield-value">{value ?? children}</div>
  </div>
);

export default DataField;
