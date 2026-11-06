(() => {
  try {
    const storedTheme = localStorage.getItem("folio-theme") || "system";
    const theme = ["light", "dark", "system"].includes(storedTheme) ? storedTheme : "system";
    const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    const storedSize = localStorage.getItem("folio-size") || "standard";
    const size = storedSize === "large" ? "large" : "standard";
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.documentElement.dataset.textSize = size;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", dark ? "#0c0e0b" : "#eff0ec");
  } catch (error) {
    /* localStorage is unavailable on some file:// origins. The document still works. */
  }
})();
