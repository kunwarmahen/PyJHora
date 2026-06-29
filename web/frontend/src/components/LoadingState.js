import React from "react";
import { useTranslation } from "react-i18next";
import "../styles/Shared.css";

/** Shared centered loading spinner with an optional message (defaults to the
 * translated "Loading…"). */
export const LoadingState = ({ message }) => {
  const { t } = useTranslation();
  const text = message ?? t("common.loading");
  return (
    <div className="loading-state">
      <div className="loading-spinner" />
      {text && <p>{text}</p>}
    </div>
  );
};

export default LoadingState;
