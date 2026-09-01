/** @odoo-module */
import {ListRenderer} from "@web/views/list/list_renderer";
import {browser} from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";

patch(ListRenderer.prototype, {
    /**
     * @override
     */
    computeColumnWidthsFromContent() {
        const columnWidths =  super.computeColumnWidthsFromContent(...arguments);
        const table = this.tableRef ? this.tableRef.el : null;
        if (!table) return columnWidths;
        const thElements = [...table.querySelectorAll("thead th")];
        thElements.forEach((el, elIndex) => {
            const fieldName = el.dataset ? el.dataset.name : (window.$ ? window.$(el).data("name") : null);
            if (
                !el.classList.contains("o_list_button") &&
                this.props.list && this.props.list.resModel &&
                fieldName &&
                browser.localStorage
            ) {
                const storedWidth = browser.localStorage.getItem(
                    `odoo.columnWidth.${this.props.list.resModel}.${fieldName}`
                );
                if (storedWidth) {
                    columnWidths[elIndex] = parseInt(storedWidth, 10);
                }
            }
        });
        return columnWidths;
    },

    /**
     * @override
     */
    onStartResize(ev) {
        super.onStartResize(...arguments);

        const resizeStoppingEvents = ["keydown", "mousedown", "mouseup"];
        const thEl = ev.target ? ev.target.closest("th") : null;
        if (!thEl) {
            return;
        }
        const saveWidth = (saveWidthEv) => {
            if (saveWidthEv.type === "mousedown" && saveWidthEv.which === 1) {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            const fieldName = thEl.dataset ? thEl.dataset.name : (window.$ ? window.$(thEl).data("name") : undefined);
            if (this.props.list && this.props.list.resModel && fieldName && browser.localStorage) {
                browser.localStorage.setItem(
                    "odoo.columnWidth." + this.props.list.resModel + "." + fieldName,
                    parseInt((thEl.style.width || "0").replace("px", ""), 10) || 0
                );
            }
            for (const eventType of resizeStoppingEvents) {
                browser.removeEventListener(eventType, saveWidth);
            }
            if (document.activeElement) {
                document.activeElement.blur();
            }
        };
        for (const eventType of resizeStoppingEvents) {
            browser.addEventListener(eventType, saveWidth);
        }
    },
});