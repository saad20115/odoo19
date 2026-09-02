/** @odoo-module */
const { Component } = owl;
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRef, useState } from "@odoo/owl";
const actionRegistry = registry.category("actions");



class ArcgisDashboard extends owl.Component {
    async setup() {
        super.setup(...arguments);
        this.initial_render = true;
        this.orm = useService('orm');
        this.action = useService('action');
        this.state = useState({
            orders: [{id: 0, name: 'امر عمل 1'},{id: 1, name: 'امر عمل 2'},{id: 2, name: 'امر عمل 3'},{id: 3, name: 'امر عمل 2'},{id: 4, name: 'امر عمل 3'},{id: 5, name: 'امر عمل 2'},{id: 6, name: 'امر عمل 3'},{id: 7, name: 'امر عمل 2'},{id: 8, name: 'امر عمل 3'},{id: 9, name: 'امر عمل 2'},{id: 10, name: 'امر عمل 3'},{id: 11, name: 'امر عمل 2'},{id: 12, name: 'امر عمل 3'},{id: 13, name: 'امر عمل 2'},{id: 14, name: 'امر عمل 3'},{id: 15, name: 'امر عمل 15'},{id: 16, name: 'امر عمل 16'}],
        });

        

    }
    
    SideBySide () {
        var map = document.getElementById("map");
        var list = document.getElementById("list");
        if(map.classList.contains("col-md-12")) {
            map.classList.remove("col-md-12");
            list.classList.remove("col-md-12");
            map.classList.add("col-md-4");
            list.classList.add("col-md-8");
        }
        else {
            map.classList.remove("col-md-4");
            list.classList.remove("col-md-8");
            map.classList.add("col-md-12");
            list.classList.add("col-md-12");
        }
    }





	}
ArcgisDashboard.template = 'arcgis_dashboard_template_new';
actionRegistry.add("arcgis_dashboard", ArcgisDashboard);
