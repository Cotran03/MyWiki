(() => {
    "use strict";

    const labels = { auto: "자동", light: "라이트", dark: "다크" };
    const order = ["auto", "light", "dark"];
    const toggle = document.querySelector("#theme-toggle");
    const media = window.matchMedia("(prefers-color-scheme: dark)");

    const applyTheme = (preference) => {
        const resolved = preference === "auto"
            ? (media.matches ? "dark" : "light")
            : preference;
        document.documentElement.dataset.bsTheme = resolved;
        document.documentElement.dataset.themePreference = preference;
        localStorage.setItem("mywiki-theme", preference);
        const label = document.querySelector("[data-theme-label]");
        if (label) label.textContent = labels[preference];
        if (toggle) toggle.setAttribute("aria-label", `화면 테마 변경, 현재 ${labels[preference]}`);
    };

    if (toggle) {
        applyTheme(document.documentElement.dataset.themePreference || "auto");
        toggle.addEventListener("click", () => {
            const current = document.documentElement.dataset.themePreference || "auto";
            const next = order[(order.indexOf(current) + 1) % order.length];
            applyTheme(next);
        });
    }

    media.addEventListener("change", () => {
        if (document.documentElement.dataset.themePreference === "auto") applyTheme("auto");
    });

    document.addEventListener("keydown", (event) => {
        const target = event.target;
        const editing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;

        if (event.key === "/" && !editing && !event.ctrlKey && !event.metaKey && !event.altKey) {
            const search = document.querySelector("#global-search, #page-search");
            if (search) {
                event.preventDefault();
                search.focus();
            }
        }

        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
            const form = document.querySelector("[data-save-shortcut]");
            if (form) {
                event.preventDefault();
                form.requestSubmit();
            }
        }
    });

    document.querySelectorAll("[data-history-back]").forEach((button) => {
        button.addEventListener("click", () => window.history.back());
    });
})();
