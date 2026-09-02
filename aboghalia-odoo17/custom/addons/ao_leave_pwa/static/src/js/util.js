/* global window */
(function () {
  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, '&#96;');
  }

  window.LeaveSafe = { escapeHtml, escapeAttr };

  const HOURS_PER_WORK_DAY = 8;

  function toHours(days, hoursPerDay) {
    const hpd = HOURS_PER_WORK_DAY;
    const hours = Number(days || 0) * hpd;
    return Math.round(hours * 10) / 10;
  }

  function formatDays(days, precision) {
    const d = Number(days || 0);
    const p = typeof precision === 'number' ? precision : 1;
    return d.toFixed(p);
  }

  function daysWithHours(days, hoursPerDay, t, precision) {
    const daysText = formatDays(days, precision);
    const hours = toHours(days, HOURS_PER_WORK_DAY);
    const hoursText = Number.isInteger(hours) ? String(hours) : hours.toFixed(1);
    const hoursLabel = t ? t('hours') : 'hours';
    const daysLabel = t ? t('days') : 'days';
    return `${daysText} ${daysLabel} (${hoursText} ${hoursLabel})`;
  }

  window.LeaveFormat = {
    HOURS_PER_WORK_DAY,
    toHours,
    formatDays,
    daysWithHours,
  };
})();
