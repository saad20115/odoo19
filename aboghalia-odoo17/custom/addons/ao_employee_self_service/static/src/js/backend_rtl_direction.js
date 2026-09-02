/** @odoo-module **/
import { registry } from "@web/core/registry";

export const rtlService = {
    dependencies: [],
    start() {
        /**
         * Determine initial direction from session info or lang attribute,
         * then apply it once. Debounced observer ensures OWL re-renders
         * don't trigger an infinite loop.
         */
        let isEnforcing = false;

        function enforceDirection() {
            if (isEnforcing) return;      // guard against re-entrancy
            isEnforcing = true;

            try {
                const htmlEl = document.documentElement;
                const body = document.body;
                if (!htmlEl || !body) return;

                // Determine desired direction
                const currentDir = htmlEl.getAttribute("dir");
                const bodyHasRtl = body.classList.contains("o_rtl");
                const sessionLang =
                    window.odoo &&
                    window.odoo.__session_info__ &&
                    window.odoo.__session_info__.user_context &&
                    window.odoo.__session_info__.user_context.lang;

                const isRTL =
                    currentDir === "rtl" ||
                    bodyHasRtl ||
                    (sessionLang && sessionLang.startsWith("ar"));

                const dir = isRTL ? "rtl" : "ltr";

                // Apply only if needed (avoid unnecessary DOM writes)
                if (htmlEl.getAttribute("dir") !== dir) {
                    htmlEl.setAttribute("dir", dir);
                }
                if (isRTL && !body.classList.contains("o_rtl")) {
                    body.classList.add("o_rtl");
                }
            } finally {
                isEnforcing = false;
            }
        }

        // Run once at service startup
        enforceDirection();

        // Debounced observer — fires at most once per 200ms
        let timer = null;
        const debouncedEnforce = () => {
            if (timer) return;
            timer = setTimeout(() => {
                timer = null;
                enforceDirection();
            }, 200);
        };

        // Only watch for class/dir attribute changes on <html> and <body>
        // Do NOT observe subtree/childList to avoid flooding.
        const observer = new MutationObserver(debouncedEnforce);
        if (document.documentElement) {
            observer.observe(document.documentElement, {
                attributes: true,
                attributeFilter: ["dir", "class"],
            });
        }
        if (document.body) {
            observer.observe(document.body, {
                attributes: true,
                attributeFilter: ["class", "dir"],
            });
        }
    },
};

registry.category("services").add("rtlService", rtlService);
