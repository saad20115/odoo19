# -*- coding: utf-8 -*-
import base64
import logging
from datetime import datetime

from odoo import api, models, _, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployeeAttendanceGrid(models.Model):
    _inherit = "hr.employee.attendance.grid"

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

        # get_attendance_data / _get_employees expect camelCase filter keys.
        grid_filters = dict(normalized_filters)
        if grid_filters.get("department_id"):
            grid_filters["departmentId"] = grid_filters["department_id"]
        if grid_filters.get("employee_name"):
            grid_filters["employeeName"] = grid_filters["employee_name"]
        if grid_filters.get("status_filter"):
            grid_filters["statusFilter"] = grid_filters["status_filter"]

        _logger.info("=" * 80)
        _logger.info("PDF EXPORT - Filters (raw): %s", filters)
        _logger.info("PDF EXPORT - Filters (normalized): %s", normalized_filters)

        grid_data = self.get_attendance_data(
            year=year,
            month=month,
            filters=grid_filters,
            pagination=pagination,
        )

        if not grid_data or not grid_data.get("success"):
            raise UserError(grid_data.get("error") or _("Failed to build attendance export data."))

        employees = grid_data.get("employees", []) or []
        if not employees:
            _logger.warning("No employees match the selected filters.")
            raise UserError(_("No employees match the selected filters. Please adjust filters and try again."))

        attendance_data = grid_data.get("attendance_data", {}) or {}
        monthly_summaries = grid_data.get("monthly_summaries", {}) or {}

        emp_ids = [e.get("id") for e in employees if e.get("id")]
        if not emp_ids:
            raise UserError(_("No employees match the selected filters. Please adjust filters and try again."))

        active_records = self.env["hr.employee"].sudo().with_context(active_test=True).search([
            ("id", "in", emp_ids),
            ("active", "=", True),
            ("resource_id.active", "=", True),
        ])
        allowed_ids = set(active_records.ids)

        employees = [e for e in employees if e.get("id") in allowed_ids]

        dept_id = normalized_filters.get("department_id")
        emp_name = (normalized_filters.get("employee_name") or "").strip().lower()
        company_id = normalized_filters.get("company_id")
        employee_id = normalized_filters.get("employee_id")

        allowed = active_records
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
