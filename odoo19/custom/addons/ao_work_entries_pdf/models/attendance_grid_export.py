# -*- coding: utf-8 -*-
import base64
import logging
from datetime import date, datetime

from odoo import api, models, _, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployeeAttendanceGrid(models.Model):
    _inherit = "hr.employee.attendance.grid"

    @api.model
    def _normalize_visible_employee_ids(self, filters):
        filters = filters or {}
        raw_ids = (
            filters.get("visibleEmployeeIds")
            or filters.get("visible_employee_ids")
            or []
        )
        if isinstance(raw_ids, str):
            raw_ids = [part.strip() for part in raw_ids.split(",") if part.strip()]

        visible_ids = []
        for raw_id in raw_ids:
            try:
                visible_ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue
        return visible_ids

    @api.model
    def _filter_pdf_employees(self, employees, year, month, visible_ids=None):
        """Keep only employees that are visible on the grid and not archived."""
        month_start = date(int(year), int(month), 1)
        employee_ids = visible_ids or [e.get("id") for e in employees if e.get("id")]
        if not employee_ids:
            return [], set()

        records = self.env["hr.employee"].sudo().with_context(active_test=False).browse(employee_ids)
        eligible_ids = set()
        for emp in records:
            if not emp.exists():
                continue
            if not emp.active:
                continue
            if emp.resource_id and not emp.resource_id.active:
                continue
            if emp.departure_date and emp.departure_date < month_start:
                continue
            eligible_ids.add(emp.id)

        if visible_ids:
            eligible_ids &= set(visible_ids)

        filtered_employees = [e for e in employees if e.get("id") in eligible_ids]
        return filtered_employees, eligible_ids

    @api.model
    def export_attendance_data(self, year, month, format="xlsx", filters=None, pagination=None):
        if (format or "").lower() != "pdf":
            return super().export_attendance_data(
                year, month, format=format, filters=filters
            )

        filters = filters or {}
        pagination = pagination or {"page": 1, "page_size": "all"}

        normalized_filters = dict(filters or {})

        if "employeeName" in normalized_filters and "employee_name" not in normalized_filters:
            normalized_filters["employee_name"] = (normalized_filters.pop("employeeName") or "").strip()

        if "statusFilter" in normalized_filters and "status_filter" not in normalized_filters:
            normalized_filters["status_filter"] = (normalized_filters.pop("statusFilter") or "").strip()

        if "departmentId" in normalized_filters and "department_id" not in normalized_filters:
            normalized_filters["department_id"] = normalized_filters.pop("departmentId")

        if "companyId" in normalized_filters and "company_id" not in normalized_filters:
            normalized_filters["company_id"] = normalized_filters.pop("companyId")

        if "employeeId" in normalized_filters and "employee_id" not in normalized_filters:
            normalized_filters["employee_id"] = normalized_filters.pop("employeeId")

        def _to_int(v):
            try:
                return int(v) if v not in (None, "", False) else False
            except Exception:
                return False

        normalized_filters["department_id"] = _to_int(normalized_filters.get("department_id"))
        normalized_filters["company_id"] = _to_int(normalized_filters.get("company_id"))
        normalized_filters["employee_id"] = _to_int(normalized_filters.get("employee_id"))
        normalized_filters["employee_name"] = (normalized_filters.get("employee_name") or "").strip()
        normalized_filters["status_filter"] = (normalized_filters.get("status_filter") or "").strip()

        visible_ids = self._normalize_visible_employee_ids(filters)

        # get_attendance_data / _get_employees expect camelCase filter keys.
        grid_filters = dict(normalized_filters)
        grid_filters.pop("visibleEmployeeIds", None)
        grid_filters.pop("visible_employee_ids", None)
        if grid_filters.get("department_id"):
            grid_filters["departmentId"] = grid_filters["department_id"]
        if grid_filters.get("employee_name"):
            grid_filters["employeeName"] = grid_filters["employee_name"]
        if grid_filters.get("status_filter"):
            grid_filters["statusFilter"] = grid_filters["status_filter"]

        _logger.info("=" * 80)
        _logger.info("PDF EXPORT - Filters (raw): %s", filters)
        _logger.info("PDF EXPORT - Filters (normalized): %s", normalized_filters)

        _logger.info("PDF EXPORT - Visible employee IDs: %s", visible_ids)

        fetch_pagination = (
            {"page": 1, "page_size": "all"}
            if visible_ids
            else pagination
        )

        grid_data = self.get_attendance_data(
            year=year,
            month=month,
            filters=grid_filters,
            pagination=fetch_pagination,
        )

        if not grid_data or not grid_data.get("success"):
            raise UserError(grid_data.get("error") or _("Failed to build attendance export data."))

        employees = grid_data.get("employees", []) or []
        if not employees:
            _logger.warning("No employees match the selected filters.")
            raise UserError(_("No employees match the selected filters. Please adjust filters and try again."))

        attendance_data = grid_data.get("attendance_data", {}) or {}
        monthly_summaries = grid_data.get("monthly_summaries", {}) or {}

        employees, allowed_ids = self._filter_pdf_employees(
            employees, year, month, visible_ids=visible_ids or None
        )

        if visible_ids and not employees:
            visible_records = self.env["hr.employee"].sudo().with_context(active_test=False).browse(visible_ids)
            emp_by_id = {emp.id: emp for emp in visible_records if emp.exists()}
            employees = []
            for emp_id in visible_ids:
                emp = emp_by_id.get(emp_id)
                if not emp or emp.id not in allowed_ids:
                    continue
                employees.append({
                    "id": emp.id,
                    "name": emp.name,
                    "department_id": emp.department_id.id if emp.department_id else False,
                    "department_name": emp.department_id.name if emp.department_id else "",
                    "work_email": emp.work_email or "",
                    "user_id": emp.user_id.id if emp.user_id else False,
                    "job_title": emp.job_title or "",
                    "work_phone": emp.work_phone or "",
                    "avatar_url": f"/web/image/hr.employee/{emp.id}/avatar_128",
                })

        dept_id = normalized_filters.get("department_id")
        emp_name = (normalized_filters.get("employee_name") or "").strip().lower()
        company_id = normalized_filters.get("company_id")
        employee_id = normalized_filters.get("employee_id")

        if allowed_ids:
            allowed = self.env["hr.employee"].sudo().with_context(active_test=False).browse(list(allowed_ids))
            if company_id:
                allowed = allowed.filtered(lambda e: e.company_id and e.company_id.id == company_id)
            if dept_id:
                allowed = allowed.filtered(lambda e: e.department_id and e.department_id.id == dept_id)
            if employee_id:
                allowed = allowed.filtered(lambda e: e.id == employee_id)
            if emp_name:
                allowed = allowed.filtered(lambda e: (e.name or "").lower().find(emp_name) != -1)
            allowed_ids = set(allowed.ids)
            employees = [e for e in employees if e.get("id") in allowed_ids]

        def _key_to_int(k):
            try:
                return int(k)
            except Exception:
                return None

        attendance_data = {
            k: v for k, v in attendance_data.items()
            if (_key_to_int(k) in allowed_ids) or (k in allowed_ids)
        }
        monthly_summaries = {
            k: v for k, v in monthly_summaries.items()
            if (_key_to_int(k) in allowed_ids) or (k in allowed_ids)
        }

        if not employees:
            raise UserError(_("No employees match the selected filters. Please adjust filters and try again."))

        allowed = self.env["hr.employee"].sudo().with_context(active_test=False).browse(list(allowed_ids))
        emp_map = {emp.id: emp for emp in allowed}
        for e in employees:
            emp = emp_map.get(e.get("id"))
            if not emp:
                e["image_base64"] = False
                e["department_name"] = False
                e["job_title"] = False
                continue

            img = emp.image_128
            e["image_base64"] = (
                img.decode("utf-8")
                if isinstance(img, (bytes, bytearray))
                else (img or False)
            )
            e["department_name"] = emp.department_id.name if emp.department_id else False
            e["job_title"] = emp.job_title or (emp.job_id.name if emp.job_id else False)

        report_ref = "ao_work_entries_pdf.report_attendance_grid_pdf"
        report = self.env["ir.actions.report"]._get_report(report_ref)

        company = self.env.company
        print_date = fields.Datetime.context_timestamp(
            self, datetime.now()
        ).strftime("%d/%m/%Y")

        values = {
            "docs": [company],
            "doc_ids": [company.id],
            "doc_model": "res.company",
            "company": company,
            "employees": employees,
            "days_in_month": grid_data.get("days_in_month", []),
            "attendance_data": attendance_data,
            "monthly_summaries": monthly_summaries,
            "year": grid_data.get("year"),
            "month": grid_data.get("month"),
            "month_name": grid_data.get("month_name", ""),
            "statistics": grid_data.get("statistics", {}),
            "print_date": print_date,
        }

        html = self.env["ir.qweb"]._render(report.report_name, values)

        pdf_content = self.env["ir.actions.report"]._run_wkhtmltopdf(
            [html],
            landscape=True,
            specific_paperformat_args={
                "data-report-margin-top": 10,
                "data-report-margin-bottom": 10,
                "data-report-margin-left": 8,
                "data-report-margin-right": 8,
                "data-report-dpi": 96,
                "data-report-header-spacing": 0,
            },
        )

        filename = f"Attendance_Grid_{int(year)}_{int(month):02d}.pdf"

        return {
            "success": True,
            "filename": filename,
            "mimetype": "application/pdf",
            "file_content": base64.b64encode(pdf_content).decode("utf-8"),
        }
