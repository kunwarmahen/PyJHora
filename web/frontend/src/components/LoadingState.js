import React from "react";
import "../styles/Shared.css";

/** Shared centered loading spinner with an optional message. */
export const LoadingState = ({ message = "Loading…" }) => (
  <div className="loading-state">
    <div className="loading-spinner" />
    {message && <p>{message}</p>}
  </div>
);

export default LoadingState;
