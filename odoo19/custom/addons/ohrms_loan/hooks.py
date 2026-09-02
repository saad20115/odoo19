# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import logging

_logger = logging.getLogger(__name__)


def migrate_loan_line_links(cr):
    """Copy legacy loan_line_id values into loan_line_ids (idempotent)."""
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'hr_payslip_input'
          AND column_name = 'loan_line_id'
    """)
    if not cr.fetchone():
        _logger.info(
            "ohrms_loan: skip loan_line migration, column loan_line_id missing")
        return

    cr.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'hr_payslip_input_loan_line_rel'
        )
    """)
    if not cr.fetchone()[0]:
        _logger.info(
            "ohrms_loan: skip loan_line migration, M2M table missing")
        return

    cr.execute("""
        INSERT INTO hr_payslip_input_loan_line_rel
            (payslip_input_id, loan_line_id)
        SELECT i.id, i.loan_line_id
        FROM hr_payslip_input i
        WHERE i.loan_line_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM hr_payslip_input_loan_line_rel r
              WHERE r.payslip_input_id = i.id
                AND r.loan_line_id = i.loan_line_id
          )
    """)
    _logger.info(
        "ohrms_loan: migrated %s payslip input loan line link(s)",
        cr.rowcount)


def post_init_hook(cr, registry):
    """Run on module install; safe if called again."""
    migrate_loan_line_links(cr)
