/* Safe first-paint preference bootstrap. Loaded before styles.css; no inline
   script or build step is required. Vue owns live listeners after mount. */
(function () {
  "use strict";

  var root = document.documentElement;
  var themePreference = "system";
  var textSize = "standard";
  try {
    var savedTheme = window.localStorage.getItem("skillsmgr-theme");
    var savedSize = window.localStorage.getItem("skillsmgr-text-size");
    if (savedTheme === "light" || savedTheme === "dark" || savedTheme === "system") themePreference = savedTheme;
    if (savedSize === "large" || savedSize === "standard") textSize = savedSize;
  } catch (e) {
    // Private browsing and storage policy failures use safe defaults.
  }

  var systemTheme = "light";
  try {
    systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch (e) {
    // Missing matchMedia or policy failures use light as the deterministic fallback.
  }

  try {
    root.dataset.themePreference = themePreference;
    root.dataset.theme = themePreference === "system" ? systemTheme : themePreference;
    root.dataset.textSize = textSize;
  } catch (e) {
    // The document root is present in normal HTML; leave its static defaults if not.
  }
}());
