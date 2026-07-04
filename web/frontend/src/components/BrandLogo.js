import React from "react";
import { SITE_TITLE } from "../config/branding";

// The app's built brand mark (public/icon-192.png — the saffron sunburst badge),
// used wherever the brand appears instead of a generic star. The PNG already has
// rounded corners baked in, so it renders as a self-contained badge.
export const BrandLogo = ({ size = 24, className = "" }) => (
  <img
    src={`${process.env.PUBLIC_URL}/icon-192.png`}
    alt={SITE_TITLE}
    width={size}
    height={size}
    className={className}
    style={{ display: "block", flexShrink: 0 }}
  />
);
