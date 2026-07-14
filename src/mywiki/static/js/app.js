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

    document.querySelectorAll("[data-markdown-preview]").forEach((workspace) => {
        const form = workspace.closest("form");
        const source = workspace.querySelector("[data-markdown-source]");
        const editorPanel = workspace.querySelector("[data-markdown-editor-panel]");
        const previewPanel = workspace.querySelector("[data-markdown-preview-panel]");
        const editButton = workspace.querySelector("[data-markdown-edit-button]");
        const previewButton = workspace.querySelector("[data-markdown-preview-button]");
        const status = workspace.querySelector("[data-markdown-preview-status]");
        const previewUrl = workspace.dataset.previewUrl;

        if (!form || !source || !editorPanel || !previewPanel || !editButton || !previewButton || !previewUrl) {
            return;
        }

        let lastRenderedSource = null;
        let previewRequest = null;

        const showEmptyPreview = () => {
            const message = document.createElement("p");
            message.className = "markdown-preview-empty";
            message.textContent = "아직 미리볼 내용이 없습니다.";
            previewPanel.replaceChildren(message);
        };

        const showMode = (mode) => {
            const previewing = mode === "preview";
            editorPanel.hidden = previewing;
            previewPanel.hidden = !previewing;
            editButton.classList.toggle("active", !previewing);
            previewButton.classList.toggle("active", previewing);
            editButton.setAttribute("aria-pressed", String(!previewing));
            previewButton.setAttribute("aria-pressed", String(previewing));
        };

        const renderPreview = async () => {
            const markdown = source.value;
            if (markdown === lastRenderedSource) return;

            if (previewRequest) previewRequest.abort();
            const requestController = new AbortController();
            previewRequest = requestController;
            previewPanel.setAttribute("aria-busy", "true");
            if (status) {
                status.classList.remove("text-danger");
                status.textContent = "미리보기를 만드는 중…";
            }

            const body = new FormData();
            const csrfToken = form.querySelector("input[name='csrf_token']");
            if (csrfToken) body.append("csrf_token", csrfToken.value);
            body.append("body_markdown", markdown);

            try {
                const response = await fetch(previewUrl, {
                    method: "POST",
                    body,
                    signal: requestController.signal,
                    credentials: "same-origin",
                    headers: { "X-Requested-With": "fetch" },
                });
                if (!response.ok) throw new Error(`Preview request failed: ${response.status}`);

                const result = await response.json();
                if (result.html) {
                    previewPanel.innerHTML = result.html;
                } else {
                    showEmptyPreview();
                }
                lastRenderedSource = markdown;
                if (status) status.textContent = "현재 내용 기준";
            } catch (error) {
                if (error.name === "AbortError") return;
                lastRenderedSource = null;
                const message = document.createElement("p");
                message.className = "markdown-preview-error";
                message.textContent = "미리보기를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
                previewPanel.replaceChildren(message);
                if (status) {
                    status.classList.add("text-danger");
                    status.textContent = "미리보기 오류";
                }
            } finally {
                if (previewRequest === requestController) {
                    previewPanel.removeAttribute("aria-busy");
                    previewRequest = null;
                }
            }
        };

        editButton.addEventListener("click", () => showMode("edit"));
        previewButton.addEventListener("click", () => {
            showMode("preview");
            renderPreview();
        });
    });
})();
