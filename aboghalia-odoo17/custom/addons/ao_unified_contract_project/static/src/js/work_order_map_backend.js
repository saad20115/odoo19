/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class UnifiedContractMapBackendAction extends Component {
    static template = "ao_unified_contract_project.WorkOrderMapBackendTemplate";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.mapRef = useRef("mapContainer");
        this.map = null;
        this.mapMarkers = {};
        this.workOrders = [];

        this.state = useState({
            searchQuery: "",
        });

        onWillStart(async () => {
            await this.loadWorkOrderData();
        });

        onMounted(() => {
            this.initLeafletMap();
        });
    }

    get filteredWorkOrders() {
        const query = (this.state.searchQuery || "").trim().toLowerCase();
        if (!query) {
            return this.workOrders;
        }
        return this.workOrders.filter(wo => {
            return (
                (wo.number && wo.number.toLowerCase().includes(query)) ||
                (wo.projectName && wo.projectName.toLowerCase().includes(query)) ||
                (wo.contractorName && wo.contractorName.toLowerCase().includes(query)) ||
                (wo.stageName && wo.stageName.toLowerCase().includes(query))
            );
        });
    }

    onSearchInput() {
        this.updateMapMarkersVisibility();
    }

    clearSearch() {
        this.state.searchQuery = "";
        this.updateMapMarkersVisibility();
    }

    updateMapMarkersVisibility() {
        if (!this.map) return;

        const filteredIds = new Set(this.filteredWorkOrders.map(wo => wo.id));
        const visibleBounds = [];

        this.workOrders.forEach(wo => {
            const marker = this.mapMarkers[wo.id];
            if (marker) {
                if (filteredIds.has(wo.id)) {
                    if (!this.map.hasLayer(marker)) {
                        marker.addTo(this.map);
                    }
                    visibleBounds.push([wo.lat, wo.lng]);
                } else {
                    if (this.map.hasLayer(marker)) {
                        this.map.removeLayer(marker);
                    }
                }
            }
        });

        if (visibleBounds.length > 0) {
            this.map.fitBounds(visibleBounds, { padding: [50, 50] });
        }
    }

    async loadWorkOrderData() {
        try {
            const data = await this.orm.searchRead(
                "unified.contract.work.order",
                [],
                [
                    "id", "name", "work_order_number", "project_id", 
                    "contractor_id", "stage_id", "stage_5_status", 
                    "progress", "coordinate_x", "coordinate_y", "state",
                    "permit_alert_status"
                ]
            );
            
            this.workOrders = data.map(wo => {
                let lat = 21.5433;
                let lng = 39.1728;
                if (wo.coordinate_y) {
                    const parsedLat = parseFloat(String(wo.coordinate_y).trim());
                    if (!isNaN(parsedLat)) lat = parsedLat;
                }
                if (wo.coordinate_x) {
                    const parsedLng = parseFloat(String(wo.coordinate_x).trim());
                    if (!isNaN(parsedLng)) lng = parsedLng;
                }

                // Stage & Status Color Logic
                let pinColor = "#f59e0b"; // Yellow default (Stage 1 / Draft)
                let stageName = wo.stage_id ? wo.stage_id[1] : "جديد / إسناد";
                
                if (wo.state === 'late' || wo.permit_alert_status === 'expired' || wo.stage_5_status === 'late') {
                    pinColor = "#ef4444"; // Red for Late / Expired
                } else if (wo.state === 'done' || wo.stage_5_status === 'paid') {
                    pinColor = "#10b981"; // Green for Paid / Done
                } else if (wo.stage_id) {
                    const sName = wo.stage_id[1];
                    if (sName.includes("إسناد") || sName.includes("1")) {
                        pinColor = "#f59e0b"; // Yellow
                    } else if (sName.includes("كشف") || sName.includes("تصاريح") || sName.includes("2")) {
                        pinColor = "#f97316"; // Orange
                    } else if (sName.includes("تنفيذ") || sName.includes("3")) {
                        pinColor = "#3b82f6"; // Blue
                    } else if (sName.includes("إغلاق") || sName.includes("وثائق") || sName.includes("4")) {
                        pinColor = "#8b5cf6"; // Purple
                    } else if (sName.includes("فوترة") || sName.includes("تحصيل") || sName.includes("5")) {
                        pinColor = "#06b6d4"; // Cyan
                    }
                }

                return {
                    ...wo,
                    number: wo.work_order_number || wo.name || `#${wo.id}`,
                    projectName: wo.project_id ? wo.project_id[1] : "غير محدد",
                    contractorName: wo.contractor_id ? wo.contractor_id[1] : "غير محدد",
                    stageName: stageName,
                    lat: lat,
                    lng: lng,
                    pinColor: pinColor,
                };
            });
        } catch (e) {
            console.error("Failed to load map work order data:", e);
        }
    }

    initLeafletMap() {
        if (!this.mapRef.el) return;

        if (typeof L === "undefined") {
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
            document.head.appendChild(link);

            const script = document.createElement("script");
            script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
            script.onload = () => this.renderMarkers();
            document.head.appendChild(script);
        } else {
            this.renderMarkers();
        }
    }

    renderMarkers() {
        if (!this.mapRef.el || typeof L === "undefined") return;

        if (this.map) {
            this.map.remove();
        }

        const mapEl = this.mapRef.el;
        mapEl.style.width = "100%";
        mapEl.style.height = "100%";

        this.map = L.map(mapEl, {
            zoomControl: true,
            attributionControl: true,
        }).setView([21.5433, 39.1728], 11);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "© OpenStreetMap"
        }).addTo(this.map);

        const bounds = [];
        this.workOrders.forEach(wo => {
            bounds.push([wo.lat, wo.lng]);

            // Create dynamic colored SVG Pin Icon
            const customIcon = L.divIcon({
                className: "custom-leaflet-pin",
                html: `
                    <div style="
                        background-color: ${wo.pinColor};
                        width: 30px;
                        height: 30px;
                        border-radius: 50% 50% 50% 0;
                        transform: rotate(-45deg);
                        border: 2px solid white;
                        box-shadow: 0 3px 6px rgba(0,0,0,0.3);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    ">
                        <div style="
                            width: 10px;
                            height: 10px;
                            background: white;
                            border-radius: 50%;
                            transform: rotate(45deg);
                        "></div>
                    </div>
                `,
                iconSize: [30, 30],
                iconAnchor: [15, 30],
                popupAnchor: [0, -30]
            });

            const marker = L.marker([wo.lat, wo.lng], { icon: customIcon }).addTo(this.map);

            const popupHtml = `
                <div style="font-family: system-ui, sans-serif; text-align: right; direction: rtl; min-width: 180px;">
                    <div style="font-weight: bold; color: #1e3a8a; font-size: 14px; margin-bottom: 4px;">
                        أمر عمل #${wo.number}
                    </div>
                    <div style="font-size: 12px; color: #475569; margin-bottom: 2px;">
                        <b>المشروع:</b> ${wo.projectName}
                    </div>
                    <div style="font-size: 12px; color: #475569; margin-bottom: 2px;">
                        <b>المقاول:</b> ${wo.contractorName}
                    </div>
                    <div style="font-size: 12px; color: #475569; margin-bottom: 4px;">
                        <b>المرحلة:</b> <span style="color: ${wo.pinColor}; font-weight: bold;">${wo.stageName}</span>
                    </div>
                    <div style="font-size: 12px; color: #16a34a; font-weight: bold; margin-bottom: 6px;">
                        <b>نسبة الإنجاز:</b> ${wo.progress}%
                    </div>
                    <button id="btn_open_wo_${wo.id}" class="btn btn-sm btn-primary w-100 py-1" style="font-size: 11px;">
                        فتح امر العمل ↗️
                    </button>
                </div>
            `;

            marker.bindPopup(popupHtml);
            marker.on("popupopen", () => {
                const btn = document.getElementById(`btn_open_wo_${wo.id}`);
                if (btn) {
                    btn.onclick = () => this.openWorkOrderForm(wo.id);
                }
            });

            this.mapMarkers[wo.id] = marker;
        });

        if (bounds.length > 0) {
            this.map.fitBounds(bounds, { padding: [50, 50] });
        }

        const forceResize = () => {
            if (this.map) {
                this.map.invalidateSize();
                if (bounds.length > 0) {
                    this.map.fitBounds(bounds, { padding: [50, 50] });
                }
            }
        };

        setTimeout(forceResize, 50);
        setTimeout(forceResize, 200);
        setTimeout(forceResize, 600);

        window.addEventListener("resize", forceResize);
    }

    focusOnMap(wo) {
        if (this.map && wo.lat && wo.lng) {
            this.map.invalidateSize();
            this.map.flyTo([wo.lat, wo.lng], 15, { duration: 1.2 });
            if (this.mapMarkers[wo.id]) {
                this.mapMarkers[wo.id].openPopup();
            }
        }
    }

    openWorkOrderForm(resId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "unified.contract.work.order",
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("unified_contract_work_order_map_backend", UnifiedContractMapBackendAction);
