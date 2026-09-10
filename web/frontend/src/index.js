import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import i18n, { ensureLanguage } from "./i18n";

const root = ReactDOM.createRoot(document.getElementById("root"));
const render = () =>
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );

// English is in the bundle, so this settles synchronously for most visitors;
// for hi/sa it waits on one small locale chunk so the first paint is already in
// the right language (§68.4).
ensureLanguage(i18n.language).then(render, render);

// Register the service worker (PWA / installable). Only in production builds —
// in dev it can interfere with hot-reload. Served from the app root as /sw.js.
if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(`${process.env.PUBLIC_URL}/sw.js`).catch(() => {
      /* registration failure is non-fatal — the app still works online */
    });
  });
}
