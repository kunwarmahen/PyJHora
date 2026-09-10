import React from "react";
import { useTranslation } from "react-i18next";
import "../styles/Shared.css";

/** Shared centered loading spinner with an optional message (defaults to the
 * translated "Loading…"). */
export const LoadingState = ({ message }) => {
  const { t } = useTranslation();
  const text = message ?? t("common.loading");
  return (
    // A spinner that says nothing is a blank page to a screen reader (§68.8).
    <div className="loading-state" role="status" aria-live="polite">
      <div className="loading-spinner" aria-hidden="true" />
      {text && <p>{text}</p>}
    </div>
  );
};

export default LoadingState;
