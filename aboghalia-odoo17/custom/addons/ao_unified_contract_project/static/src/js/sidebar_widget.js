/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class UnifiedContractRightSidebar extends Component {
    setup() {
        this.actionService = useService("action");
        this.state = useState({
            isCollapsed: false,
            activeAction: "action_unified_contract_project",
        });
    }

    toggleSidebar() {
        this.state.isCollapsed = !this.state.isCollapsed;
    }

    async selectMenu(actionXmlId) {
        this.state.activeAction = actionXmlId;
        await this.actionService.doAction(`ao_unified_contract_project.${actionXmlId}`, {
            clearBreadcrumbs: false,
        });
    }
}

UnifiedContractRightSidebar.template = "ao_unified_contract_project.UnifiedContractRightSidebar";
