/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ============================================================================
// BASE ANALYTICS COMPONENT WITH SHARED DATA LOADING & METRICS LOGIC
// ============================================================================
class BaseAnalyticsDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.charts = {};

        this.state = useState({
            searchQuery: "",
            selectedProjectId: "",
            selectedContractorId: "",
            selectedStageId: "",
            currentPage: 1,
            pageSize: 15,
            projects: [],
            contractors: [],
            stages: [],
            workOrders: [],
            isLoading: true,
        });

        onWillStart(async () => {
            await this.loadAllDashboardData();
        });

        onMounted(async () => {
            if (this.state.workOrders.length === 0) {
                await this.loadAllDashboardData();
            }
            this.initCharts();
        });

        useEffect(
            () => {
                if (!this.state.isLoading && typeof Chart !== "undefined") {
                    this.renderAllCharts();
                }
            },
            () => [
                this.state.searchQuery,
                this.state.selectedProjectId,
                this.state.selectedContractorId,
                this.state.selectedStageId,
                this.state.workOrders.length,
            ]
        );
    }

    get projects() { return this.state.projects; }
    get contractors() { return this.state.contractors; }
    get stages() { return this.state.stages; }
    get workOrders() { return this.state.workOrders; }

    formatMoney(val) {
        if (!val || isNaN(val)) return "0.00 ر.س";
        return new Intl.NumberFormat('ar-SA', { style: 'currency', currency: 'SAR', maximumFractionDigits: 0 }).format(val);
    }

    get filteredWorkOrders() {
        const query = (this.state.searchQuery || "").trim().toLowerCase();
        const pId = this.state.selectedProjectId ? parseInt(this.state.selectedProjectId) : null;
        const cId = this.state.selectedContractorId ? parseInt(this.state.selectedContractorId) : null;
        const sId = this.state.selectedStageId ? parseInt(this.state.selectedStageId) : null;

        return this.state.workOrders.filter(wo => {
            if (pId && wo.project_id && wo.project_id[0] !== pId) return false;
            if (cId && wo.contractor_id && wo.contractor_id[0] !== cId) return false;
            if (sId && wo.stage_id && wo.stage_id[0] !== sId) return false;

            if (query) {
                const matchNumber = wo.number && wo.number.toLowerCase().includes(query);
                const matchProject = wo.projectName && wo.projectName.toLowerCase().includes(query);
                const matchContractor = wo.contractorName && wo.contractorName.toLowerCase().includes(query);
                const matchStage = wo.stageName && wo.stageName.toLowerCase().includes(query);
                if (!matchNumber && !matchProject && !matchContractor && !matchStage) return false;
            }

            return true;
        });
    }

    get totalPages() {
        return Math.ceil(this.filteredWorkOrders.length / this.state.pageSize) || 1;
    }

    get paginatedWorkOrders() {
        const start = (this.state.currentPage - 1) * this.state.pageSize;
        return this.filteredWorkOrders.slice(start, start + this.state.pageSize);
    }

    prevPage() {
        if (this.state.currentPage > 1) {
            this.state.currentPage -= 1;
        }
    }

    nextPage() {
        if (this.state.currentPage < this.totalPages) {
            this.state.currentPage += 1;
        }
    }

    get metrics() {
        const wos = this.filteredWorkOrders;
        const totalWOs = wos.length;

        let totalProg = 0;
        let lateCount = 0;
        let totalAmount = 0;
        let paidAmount = 0;

        wos.forEach(w => {
            totalProg += (w.progress || 0);
            if (w.state === 'late' || w.permit_alert_status === 'expired' || w.stage_5_status === 'late') {
                lateCount += 1;
            }
            totalAmount += (w.amount_before_tax || 0);
            if (w.state === 'done' || w.stage_5_status === 'paid' || w.payment_status === 'paid') {
                paidAmount += (w.amount_total || w.amount_before_tax || 0);
            }
        });

        const avgProgress = totalWOs > 0 ? (totalProg / totalWOs).toFixed(1) : "0.0";
        const selectedPId = this.state.selectedProjectId ? parseInt(this.state.selectedProjectId) : null;
        const projectSet = new Set(wos.map(w => w.project_id ? w.project_id[0] : null).filter(Boolean));
        const totalProjectsCount = selectedPId ? 1 : (this.state.projects.length || projectSet.size);

        const avgWOsPerProject = totalProjectsCount > 0 ? (totalWOs / totalProjectsCount).toFixed(1) : "0.0";
        const pendingAmount = Math.max(0, totalAmount - paidAmount);
        const collectionRate = totalAmount > 0 ? ((paidAmount / totalAmount) * 100).toFixed(1) : "0.0";

        return {
            totalProjects: totalProjectsCount,
            totalWorkOrders: totalWOs,
            avgProgress: avgProgress,
            lateCount: lateCount,
            totalAmount: totalAmount,
            paidAmount: paidAmount,
            pendingAmount: pendingAmount,
            avgWOsPerProject: avgWOsPerProject,
            collectionRate: collectionRate,
        };
    }

    async loadAllDashboardData() {
        try {
            this.state.isLoading = true;

            // 1. Load Projects
            const loadedProjects = await this.orm.searchRead(
                "unified.contract.project",
                [],
                ["id", "name", "code", "state", "work_order_count"]
            );
            this.state.projects = loadedProjects || [];

            // 2. Load Work Orders
            const rawWOs = await this.orm.searchRead(
                "unified.contract.work.order",
                [],
                [
                    "id", "name", "work_order_number", "project_id", 
                    "contractor_id", "stage_id", "stage_5_status", 
                    "progress", "amount_before_tax", "amount_total",
                    "state", "permit_alert_status", "payment_status"
                ]
            );

            // 3. Load Contractors assigned to Projects or Work Orders ONLY
            const contractorIds = new Set();
            (this.state.projects || []).forEach(p => {
                if (p.contractor_id) contractorIds.add(p.contractor_id[0]);
            });
            (rawWOs || []).forEach(w => {
                if (w.contractor_id) contractorIds.add(w.contractor_id[0]);
            });

            let loadedContractors = [];
            if (contractorIds.size > 0) {
                loadedContractors = await this.orm.searchRead(
                    "res.partner",
                    [["id", "in", Array.from(contractorIds)]],
                    ["id", "name"]
                );
            } else {
                loadedContractors = await this.orm.searchRead(
                    "res.partner",
                    [["supplier_rank", ">", 0]],
                    ["id", "name"],
                    { limit: 20 }
                );
            }
            this.state.contractors = loadedContractors || [];

            // 4. Load Stages
            const loadedStages = await this.orm.searchRead(
                "unified.contract.work.order.stage",
                [],
                ["id", "name", "sequence"],
                { order: "sequence asc" }
            );
            this.state.stages = loadedStages || [];

            this.state.workOrders = (rawWOs || []).map(wo => {
                let pinColor = "#f59e0b";
                let stageName = wo.stage_id ? wo.stage_id[1] : "جديد / إسناد";
                
                if (wo.state === 'late' || wo.permit_alert_status === 'expired' || wo.stage_5_status === 'late') {
                    pinColor = "#ef4444";
                } else if (wo.state === 'done' || wo.stage_5_status === 'paid') {
                    pinColor = "#10b981";
                } else if (wo.stage_id) {
                    const sName = wo.stage_id[1];
                    if (sName.includes("إسناد") || sName.includes("1")) pinColor = "#f59e0b";
                    else if (sName.includes("كشف") || sName.includes("تصاريح") || sName.includes("2")) pinColor = "#f97316";
                    else if (sName.includes("تنفيذ") || sName.includes("3")) pinColor = "#3b82f6";
                    else if (sName.includes("إغلاق") || sName.includes("وثائق") || sName.includes("4")) pinColor = "#8b5cf6";
                    else if (sName.includes("فوترة") || sName.includes("تحصيل") || sName.includes("5")) pinColor = "#06b6d4";
                }

                return {
                    ...wo,
                    number: wo.work_order_number || wo.name || `#${wo.id}`,
                    projectName: wo.project_id ? wo.project_id[1] : "غير محدد",
                    contractorName: wo.contractor_id ? wo.contractor_id[1] : "غير محدد",
                    stageName: stageName,
                    pinColor: pinColor,
                };
            });

            this.state.isLoading = false;

        } catch (e) {
            console.error("Error loading dashboard data:", e);
            this.state.isLoading = false;
        }
    }

    onFilterChange() {
        this.state.currentPage = 1;
        this.renderAllCharts();
    }

    async refreshDashboard() {
        await this.loadAllDashboardData();
        this.renderAllCharts();
    }

    initCharts() {
        if (typeof Chart === "undefined") {
            const script = document.createElement("script");
            script.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
            script.onload = () => this.renderAllCharts();
            document.head.appendChild(script);
        } else {
            this.renderAllCharts();
        }
    }

    renderAllCharts() {}

    openWorkOrderForm(resId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "unified.contract.work.order",
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openProjectForm(resId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "unified.contract.project",
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

// ============================================================================
// 1. EXECUTIVE ANALYTICS DASHBOARD COMPONENT
// ============================================================================
export class UnifiedContractAnalyticsDashboard extends BaseAnalyticsDashboard {
    static template = "ao_unified_contract_project.AnalyticsDashboardTemplate";

    setup() {
        super.setup();
        this.stageChartRef = useRef("stageChartCanvas");
        this.progressChartRef = useRef("progressChartCanvas");
        this.financialChartRef = useRef("financialChartCanvas");
        this.permitChartRef = useRef("permitChartCanvas");
    }

    renderAllCharts() {
        if (typeof Chart === "undefined") return;

        Object.keys(this.charts).forEach(k => { try { this.charts[k].destroy(); } catch(e){} });

        const wos = this.filteredWorkOrders;

        if (this.stageChartRef.el) {
            const stageCounts = {};
            this.state.stages.forEach(s => { stageCounts[s.name] = 0; });
            wos.forEach(w => { stageCounts[w.stageName || "غير محدد"] = (stageCounts[w.stageName || "غير محدد"] || 0) + 1; });

            this.charts.stageChart = new Chart(this.stageChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(stageCounts),
                    datasets: [{ data: Object.values(stageCounts), backgroundColor: ['#f59e0b', '#f97316', '#3b82f6', '#8b5cf6', '#06b6d4', '#10b981'], borderWidth: 2 }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });
        }

        if (this.progressChartRef.el) {
            const pProg = {}, pCounts = {};
            wos.forEach(w => {
                pProg[w.projectName] = (pProg[w.projectName] || 0) + (w.progress || 0);
                pCounts[w.projectName] = (pCounts[w.projectName] || 0) + 1;
            });
            const labels = Object.keys(pProg).slice(0, 7);
            const avgData = labels.map(l => (pProg[l] / pCounts[l]).toFixed(1));

            this.charts.progressChart = new Chart(this.progressChartRef.el, {
                type: 'bar',
                data: { labels, datasets: [{ label: 'الإنجاز (%)', data: avgData, backgroundColor: '#3b82f6', borderRadius: 6 }] },
                options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', scales: { x: { max: 100 } } }
            });
        }

        if (this.financialChartRef.el) {
            const pFin = {};
            wos.forEach(w => {
                if (!pFin[w.projectName]) pFin[w.projectName] = { total: 0, paid: 0 };
                pFin[w.projectName].total += (w.amount_before_tax || 0);
                if (w.state === 'done' || w.stage_5_status === 'paid') pFin[w.projectName].paid += (w.amount_total || w.amount_before_tax || 0);
            });
            const fLabels = Object.keys(pFin).slice(0, 6);

            this.charts.financialChart = new Chart(this.financialChartRef.el, {
                type: 'bar',
                data: {
                    labels: fLabels,
                    datasets: [
                        { label: 'التقديري (ر.س)', data: fLabels.map(l => pFin[l].total), backgroundColor: '#f59e0b', borderRadius: 4 },
                        { label: 'المحصل (ر.س)', data: fLabels.map(l => pFin[l].paid), backgroundColor: '#10b981', borderRadius: 4 },
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } } }
            });
        }

        if (this.permitChartRef.el) {
            let norm = 0, warn = 0, exp = 0;
            wos.forEach(w => {
                if (w.permit_alert_status === 'expired') exp++;
                else if (w.permit_alert_status === 'warning') warn++;
                else norm++;
            });

            this.charts.permitChart = new Chart(this.permitChartRef.el, {
                type: 'pie',
                data: { labels: ['ساري 🟢', 'تنبيه ⚠️', 'منتهي 🔴'], datasets: [{ data: [norm, warn, exp], backgroundColor: ['#10b981', '#f59e0b', '#ef4444'] }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });
        }
    }
}

// ============================================================================
// 2. WORK ORDERS ANALYTICAL DASHBOARD COMPONENT
// ============================================================================
export class UnifiedContractWorkOrdersDashboard extends BaseAnalyticsDashboard {
    static template = "ao_unified_contract_project.WorkOrdersDashboardTemplate";

    setup() {
        super.setup();
        this.stageChartRef = useRef("stageChartCanvas");
        this.permitChartRef = useRef("permitChartCanvas");
    }

    renderAllCharts() {
        if (typeof Chart === "undefined") return;

        Object.keys(this.charts).forEach(k => { try { this.charts[k].destroy(); } catch(e){} });

        const wos = this.filteredWorkOrders;

        if (this.stageChartRef.el) {
            const stageCounts = {};
            this.state.stages.forEach(s => { stageCounts[s.name] = 0; });
            wos.forEach(w => { stageCounts[w.stageName || "غير محدد"] = (stageCounts[w.stageName || "غير محدد"] || 0) + 1; });

            this.charts.stageChart = new Chart(this.stageChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(stageCounts),
                    datasets: [{ data: Object.values(stageCounts), backgroundColor: ['#f59e0b', '#f97316', '#3b82f6', '#8b5cf6', '#06b6d4', '#10b981'], borderWidth: 2 }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });
        }

        if (this.permitChartRef.el) {
            let norm = 0, warn = 0, exp = 0;
            wos.forEach(w => {
                if (w.permit_alert_status === 'expired') exp++;
                else if (w.permit_alert_status === 'warning') warn++;
                else norm++;
            });

            this.charts.permitChart = new Chart(this.permitChartRef.el, {
                type: 'pie',
                data: { labels: ['ساري 🟢', 'تنبيه انتهاء ⚠️', 'منتهي 🔴'], datasets: [{ data: [norm, warn, exp], backgroundColor: ['#10b981', '#f59e0b', '#ef4444'] }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });
        }
    }
}

// ============================================================================
// 3. PROJECTS ANALYTICAL DASHBOARD COMPONENT
// ============================================================================
export class UnifiedContractProjectsDashboard extends BaseAnalyticsDashboard {
    static template = "ao_unified_contract_project.ProjectsDashboardTemplate";

    setup() {
        super.setup();
        this.projectWOChartRef = useRef("projectWOChartCanvas");
        this.contractorLoadChartRef = useRef("contractorLoadChartCanvas");
    }

    renderAllCharts() {
        if (typeof Chart === "undefined") return;

        Object.keys(this.charts).forEach(k => { try { this.charts[k].destroy(); } catch(e){} });

        const wos = this.filteredWorkOrders;

        if (this.projectWOChartRef.el) {
            const pWOCounts = {};
            wos.forEach(w => { pWOCounts[w.projectName] = (pWOCounts[w.projectName] || 0) + 1; });
            const labels = Object.keys(pWOCounts).slice(0, 7);

            this.charts.projectWOChart = new Chart(this.projectWOChartRef.el, {
                type: 'bar',
                data: { labels, datasets: [{ label: 'عدد أوامر العمل', data: labels.map(l => pWOCounts[l]), backgroundColor: '#3b82f6', borderRadius: 5 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }

        if (this.contractorLoadChartRef.el) {
            const cWOCounts = {};
            wos.forEach(w => { cWOCounts[w.contractorName] = (cWOCounts[w.contractorName] || 0) + 1; });
            const labels = Object.keys(cWOCounts).slice(0, 6);

            this.charts.contractorLoadChart = new Chart(this.contractorLoadChartRef.el, {
                type: 'doughnut',
                data: { labels, datasets: [{ data: labels.map(l => cWOCounts[l]), backgroundColor: ['#8b5cf6', '#06b6d4', '#3b82f6', '#f59e0b', '#10b981', '#f97316'] }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });
        }
    }
}

// ============================================================================
// 4. INVOICES & COLLECTION ANALYTICAL DASHBOARD COMPONENT
// ============================================================================
export class UnifiedContractInvoicesDashboard extends BaseAnalyticsDashboard {
    static template = "ao_unified_contract_project.InvoicesDashboardTemplate";

    setup() {
        super.setup();
        this.invoiceFinancialChartRef = useRef("invoiceFinancialChartCanvas");
        this.contractorPaidChartRef = useRef("contractorPaidChartCanvas");
    }

    renderAllCharts() {
        if (typeof Chart === "undefined") return;

        Object.keys(this.charts).forEach(k => { try { this.charts[k].destroy(); } catch(e){} });

        const wos = this.filteredWorkOrders;

        if (this.invoiceFinancialChartRef.el) {
            const pFin = {};
            wos.forEach(w => {
                if (!pFin[w.projectName]) pFin[w.projectName] = { total: 0, paid: 0 };
                pFin[w.projectName].total += (w.amount_before_tax || 0);
                if (w.state === 'done' || w.stage_5_status === 'paid') pFin[w.projectName].paid += (w.amount_total || w.amount_before_tax || 0);
            });
            const fLabels = Object.keys(pFin).slice(0, 6);

            this.charts.invoiceFinancialChart = new Chart(this.invoiceFinancialChartRef.el, {
                type: 'bar',
                data: {
                    labels: fLabels,
                    datasets: [
                        { label: 'المبالغ الكلية (ر.س)', data: fLabels.map(l => pFin[l].total), backgroundColor: '#f59e0b', borderRadius: 4 },
                        { label: 'المحصلة نقدياً (ر.س)', data: fLabels.map(l => pFin[l].paid), backgroundColor: '#10b981', borderRadius: 4 },
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } } }
            });
        }

        if (this.contractorPaidChartRef.el) {
            const cPaid = {};
            wos.forEach(w => {
                if (w.state === 'done' || w.stage_5_status === 'paid') {
                    cPaid[w.contractorName] = (cPaid[w.contractorName] || 0) + (w.amount_total || w.amount_before_tax || 0);
                }
            });
            const labels = Object.keys(cPaid).slice(0, 6);

            this.charts.contractorPaidChart = new Chart(this.contractorPaidChartRef.el, {
                type: 'pie',
                data: { labels, datasets: [{ data: labels.map(l => cPaid[l]), backgroundColor: ['#10b981', '#06b6d4', '#3b82f6', '#8b5cf6', '#f59e0b', '#f97316'] }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });
        }
    }
}

// Registry Additions
registry.category("actions").add("unified_contract_analytics_dashboard", UnifiedContractAnalyticsDashboard);
registry.category("actions").add("unified_contract_work_orders_dashboard", UnifiedContractWorkOrdersDashboard);
registry.category("actions").add("unified_contract_projects_dashboard", UnifiedContractProjectsDashboard);
registry.category("actions").add("unified_contract_invoices_dashboard", UnifiedContractInvoicesDashboard);
