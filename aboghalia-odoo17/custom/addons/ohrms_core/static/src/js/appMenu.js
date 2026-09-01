/** @odoo-module */
import { NavBar } from "@web/webclient/navbar/navbar";
import { registry } from "@web/core/registry";
import { fuzzyLookup } from "@web/core/utils/search";
import { computeAppsAndMenuItems } from "@web/webclient/menus/menu_helpers";
import { Deferred } from "@web/core/utils/concurrency";
import { onMounted, Component, useRef, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

const commandProviderRegistry = registry.category("command_provider");

patch(NavBar.prototype, {
    setup() {
        super.setup();
        this.search_input = useRef("search-input");
        this._search_def = new Deferred();
        let { apps, menuItems } = computeAppsAndMenuItems(this.menuService.getMenuAsTree("root"));
        this._apps = apps;
        this._searchableMenus = menuItems;
        this.state = useState({
            results: [],
        });
    },

    _searchMenusSchedule() {
        if (window.$) {
            window.$('.search-results').removeClass("o_hidden");
            window.$('.app-menu').addClass("o_hidden");
        }
        if (this._search_def && this._search_def.reject) {
            try { this._search_def.reject(); } catch(e) {}
        }
        this._search_def = new Deferred();
        setTimeout(() => {
            if (this._search_def) {
                this._search_def.resolve();
                this._searchMenus();
            }
        }, 50);
    },

    _searchMenus() {
        var query = this.search_input.el ? this.search_input.el.value : "";
        if (query === "") {
            if (window.$) {
                window.$('.search-container').removeClass("has-results");
                window.$('.app-menu').removeClass("o_hidden");
                window.$('.search-results').empty();
            }
            return;
        }

        var results = [];
        fuzzyLookup(query, this._apps, (menu) => menu.label)
        .forEach((menu) => {
            results.push({
                category: "apps",
                name: menu.label,
                actionID: menu.actionID,
                id: menu.id,
                webIconData: menu.webIconData,
            });
        });
        fuzzyLookup(query, this._searchableMenus, (menu) =>
            (menu.parents + " / " + menu.label).split("/").reverse().join("/"))
        .forEach((menu) => {
            results.push({
                category: "menu_items",
                name: menu.parents + " / " + menu.label,
                actionID: menu.actionID,
                id: menu.id,
            });
        });
        if (window.$) {
            window.$('.search-container').toggleClass(
                "has-results",
                Boolean(results.length)
            );
        }
        this.state.results = results;
    }
});
