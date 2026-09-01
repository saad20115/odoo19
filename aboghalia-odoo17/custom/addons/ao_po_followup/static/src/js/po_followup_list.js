/** @odoo-module */

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

/** Standard list + CSS hook class (no KPI banner). */
export class PoFollowupListController extends ListController {
    get className() {
        return `${super.className} ao_po_followup_tree`;
    }
}

registry.category("views").add("po_followup_list", {
    ...listView,
    Controller: PoFollowupListController,
});
