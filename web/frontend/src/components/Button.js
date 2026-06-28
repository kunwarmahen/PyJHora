import React from "react";
import "../styles/Shared.css";

/**
 * Themed button. variant: "primary" | "secondary" | "ghost". `block` makes it
 * full-width. `icon` is rendered before the children. Extra props (onClick,
 * disabled, title, type, …) pass through.
 */
export const Button = ({
  variant = "primary",
  block = false,
  icon,
  className = "",
  children,
  ...rest
}) => {
  const classes = ["ui-btn", `ui-btn--${variant}`, block ? "ui-btn--block" : "", className]
    .filter(Boolean)
    .join(" ");
  return (
    <button className={classes} {...rest}>
      {icon}
      {children && <span>{children}</span>}
    </button>
  );
};

export default Button;
