/** @odoo-module **/

import { jsonrpc } from "@web/core/network/rpc_service";

const MONTH_NAME_TO_NUM = {
    january: 1, february: 2, march: 3, april: 4, may: 5, june: 6,
    july: 7, august: 8, september: 9, october: 10, november: 11, december: 12,
};

function b64ToBlob(b64Data, contentType = "application/pdf") {
    const clean = (b64Data || "").includes("base64,")
        ? (b64Data.split("base64,")[1] || "")
        : (b64Data || "");
    const byteChars = atob(clean);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i);
    }
    return new Blob([new Uint8Array(byteNumbers)], { type: contentType });
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "attendance.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

function prune(obj) {
    const out = {};
    for (const [k, v] of Object.entries(obj || {})) {
        if (v === undefined || v === null) continue;
        if (typeof v === "string" && !v.trim()) continue;
        out[k] = v;
    }
    return out;
}

function getContextFromCtxSpan(buttonEl) {
    const container = buttonEl.closest(".o_attendance_grid_container");
    const ctxEl = container ? container.querySelector(".ao_attendance_grid_ctx") : null;
    if (!ctxEl) return null;

    const ds = ctxEl.dataset || {};
    const year = parseInt(ds.year || "", 10);
    const month = parseInt(ds.month || "", 10);

    const filters = {};
    if (ds.filterDepartment) {
        const deptId = parseInt(ds.filterDepartment, 10);
        if (!isNaN(deptId)) filters.departmentId = deptId;
    }
    if (ds.filterEmployee) filters.employeeName = ds.filterEmployee;
    if (ds.filterStatus) filters.statusFilter = ds.filterStatus;

    const pagination = {
        page: parseInt(ds.page || "1", 10) || 1,
        page_size: ds.pageSize || "all",
    };

    return { year, month, filters: prune(filters), pagination };
}

function getContextFromDom() {
    const titleEl = document.querySelector(".o_attendance_title h2, h2");
    let year = new Date().getFullYear();
    let month = new Date().getMonth() + 1;

    if (titleEl) {
        const titleText = titleEl.textContent || "";
        const match = titleText.match(/(\w+)\s+(\d{4})/);
        if (match) {
            const monthName = match[1].toLowerCase();
            month = MONTH_NAME_TO_NUM[monthName] || month;
            year = parseInt(match[2], 10) || year;
        }
    }

    const filters = {};

    const deptSelect = document.querySelector(".o_attendance_filters select, select.form-select");
    if (deptSelect && deptSelect.value && deptSelect.value !== "" && deptSelect.value !== "all") {
        const deptId = parseInt(deptSelect.value, 10);
        if (!isNaN(deptId)) filters.departmentId = deptId;
    }

    const empSearch = document.querySelector(".o_attendance_filters input[type='text'], input[placeholder*='employee']");
    if (empSearch && empSearch.value && empSearch.value.trim()) {
        filters.employeeName = empSearch.value.trim();
    }

    const pagination = { page: 1, page_size: "all" };

    const pageSizeSelect = document.querySelector(".o_attendance_pagination_controls select");
    if (pageSizeSelect && pageSizeSelect.value) {
        pagination.page_size = pageSizeSelect.value;
    }

    const activePageBtn = document.querySelector(".pagination .page-item.active .page-link");
    if (activePageBtn) {
        const pageNum = parseInt(activePageBtn.textContent, 10);
        if (!isNaN(pageNum)) pagination.page = pageNum;
    }

    return { year, month, filters: prune(filters), pagination };
}

function getVisibleEmployeeIds(buttonEl) {
    const container = buttonEl.closest(".o_attendance_grid_container");
    if (!container) {
        return [];
    }

    const ctxEl = container.querySelector(".ao_attendance_grid_ctx");
    const rawIds = ctxEl?.dataset?.employeeIds;
    if (rawIds) {
        return rawIds
            .split(",")
            .map((id) => parseInt(id, 10))
            .filter((id) => !isNaN(id));
    }

    const rows = container.querySelectorAll(".o_employee_row[data-employee-id]");
    const ids = [];
    const seen = new Set();
    for (const row of rows) {
        const id = parseInt(row.dataset.employeeId, 10);
        if (!isNaN(id) && !seen.has(id)) {
            seen.add(id);
            ids.push(id);
        }
    }
    return ids;
}

function getContext(buttonEl) {
    return getContextFromCtxSpan(buttonEl) || getContextFromDom(buttonEl);
}

async function exportPdf(buttonEl) {
    const ctx = getContext(buttonEl);
    const year = ctx?.year;
    const month = ctx?.month;
    const filters = { ...(ctx?.filters || {}) };
    const pagination = ctx?.pagination || { page: 1, page_size: "all" };
    const visibleEmployeeIds = getVisibleEmployeeIds(buttonEl);

    if (!year || !month) {
        alert("Could not detect the current period. Please refresh the page and try again.");
        return;
    }

    if (!visibleEmployeeIds.length) {
        alert("No employees are visible on the current page to export.");
        return;
    }

    filters.visibleEmployeeIds = visibleEmployeeIds;

    const pdfPagination = {
        page: pagination.page || 1,
        page_size: pagination.page_size ?? "all",
    };

    const result = await jsonrpc(
        "/web/dataset/call_kw/hr.employee.attendance.grid/export_attendance_data",
        {
            model: "hr.employee.attendance.grid",
            method: "export_attendance_data",
            args: [year, month, "pdf", filters, pdfPagination],
            kwargs: {},
        }
    );

    if (!result || !result.success) {
        alert("Export failed: " + (result?.error || "Unknown error"));
        return;
    }

    if (!result.file_content) {
        alert("Export failed: No file content returned");
        return;
    }

    const filename = result.filename || `Attendance_Grid_${year}_${String(month).padStart(2, "0")}.pdf`;
    const mimetype = result.mimetype || "application/pdf";
    const blob = b64ToBlob(result.file_content, mimetype);
    downloadBlob(blob, filename);
}

function isPdfButton(el) {
    return el?.classList?.contains("ao_print_pdf_btn");
}

if (!window.__AO_PDF_EXPORT_BOUND__) {
    window.__AO_PDF_EXPORT_BOUND__ = true;

    document.addEventListener("click", async (ev) => {
        const btn = ev.target?.closest?.("button");
        if (!btn || !isPdfButton(btn)) return;
        if (btn.disabled) return;

        ev.preventDefault();
        ev.stopPropagation();

        const originalText = btn.innerHTML;

        try {
            btn.disabled = true;
            btn.innerHTML = '<i class="fa fa-spinner fa-spin me-1"></i> Generating PDF...';
            await exportPdf(btn);
            btn.innerHTML = '<i class="fa fa-check me-1"></i> Done!';
            setTimeout(() => {
                btn.innerHTML = originalText;
            }, 2000);
        } catch (e) {
            btn.innerHTML = '<i class="fa fa-exclamation-triangle me-1"></i> Failed';
            setTimeout(() => {
                btn.innerHTML = originalText;
            }, 3000);
        } finally {
            btn.disabled = false;
        }
    });
}
