import React from "react";
import { useAuth } from "../contexts/AuthContext";
import { StartupRedirect } from "./StartupRedirect";
import { LandingPage } from "../pages/LandingPage";

/**
 * The app's "/" entry point.
 *
 * Signed-in visitors resume straight into the app (StartupRedirect → their
 * profile's dashboard, exactly as before). Signed-out visitors get the public
 * marketing landing page instead of being bounced to /login — the landing page
 * carries its own Log in / Get started calls-to-action.
 *
 * While auth is still resolving we render nothing rather than flashing the
 * landing page to a user who is about to be redirected.
 */
export const RootRoute = () => {
  const { user, isLoading } = useAuth();
  if (isLoading) return null;
  return user ? <StartupRedirect /> : <LandingPage />;
};

export default RootRoute;
