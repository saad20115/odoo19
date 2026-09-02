# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Ensure absence_days_manually_set exists (safe if upgrade was interrupted)."""
    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'hr_employee_monthly_summary'
          AND column_name = 'absence_days_manually_set'
        """
    )
    if cr.fetchone():
        return

    _logger.info('Adding column hr_employee_monthly_summary.absence_days_manually_set')
    cr.execute(
        """
        ALTER TABLE hr_employee_monthly_summary
        ADD COLUMN absence_days_manually_set boolean DEFAULT false
        """
    )
