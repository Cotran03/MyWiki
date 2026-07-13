(() => {
    "use strict";

    const stored = localStorage.getItem("mywiki-theme") || "auto";
    const resolved = stored === "auto"
        ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
        : stored;
    document.documentElement.dataset.bsTheme = resolved;
    document.documentElement.dataset.themePreference = stored;
})();
