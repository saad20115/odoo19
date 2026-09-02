/* global window, LeaveI18n, LeaveApi, LeaveSafe, LeaveChrome */
(function () {
  const esc = (v) => (window.LeaveSafe ? LeaveSafe.escapeHtml(v) : String(v == null ? '' : v));

  function formatMonthLabel(periodStart, lang) {
    if (!periodStart) return '—';
    const date = new Date(`${periodStart}T12:00:00`);
    const locale = lang === 'ar' ? 'ar-EG' : 'en-GB';
    return date.toLocaleDateString(locale, { month: 'long', year: 'numeric' });
  }

  function formatDateRange(fromIso, toIso, lang) {
    if (!fromIso || !toIso) return '—';
    const opts = { day: 'numeric', month: 'short', year: 'numeric' };
    const locale = lang === 'ar' ? 'ar-EG' : 'en-GB';
    const from = new Date(`${fromIso}T12:00:00`);
    const to = new Date(`${toIso}T12:00:00`);
    return `${from.toLocaleDateString(locale, opts)} - ${to.toLocaleDateString(locale, opts)}`;
  }

  function formatDays(days, precision) {
    if (days == null) return '—';
    return Number(days || 0).toFixed(typeof precision === 'number' ? precision : 1);
  }

  function renderMonthlyTable(balance, lang, t) {
    const months = (balance && balance.months) || [];
    if (!months.length) {
      return `<p class="hint">${esc(t('loading'))}</p>`;
    }
    return `
      <div class="monthly-table-wrap">
        <table class="monthly-table">
          <thead>
            <tr>
              <th>${esc(t('month'))}</th>
              <th>${esc(t('accrued'))}</th>
              <th>${esc(t('used'))}</th>
              <th>${esc(t('remaining'))}</th>
            </tr>
          </thead>
          <tbody>
            ${months.map((row) => `
              <tr class="${row.is_current ? 'current-month' : ''}${row.before_import ? ' before-import' : ''}">
                <td>${esc(formatMonthLabel(row.period_start, lang))}</td>
                <td>${row.before_import ? '—' : esc(formatDays(row.accrued, 2))}</td>
                <td>${row.before_import ? '—' : esc(formatDays(row.used, 1))}</td>
                <td>${esc(formatDays(row.remaining, 2))}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  window.LeaveScreens = window.LeaveScreens || {};
  window.LeaveScreens.balance = async function (root, app) {
    const t = (k) => LeaveI18n.t(k);
    const withNavClass = app.state.isApprover ? 'with-nav' : 'with-nav';
    root.innerHTML = `
      <div class="screen ${withNavClass}">
        ${LeaveChrome.renderHeader(app, {
          title: t('monthlyBreakdown'),
          subtitle: t('approvedOnlyHint'),
        })}
        <div class="overlap-wrap">
          <div class="card monthly-balance" id="balance-detail">
            <div class="loading">${esc(t('loading'))}</div>
          </div>
        </div>
        ${LeaveChrome.renderBottomNav(app, 'balance')}
      </div>
    `;

    LeaveChrome.wireHeader(root, app, { reloadScreen: 'balance' });
    LeaveChrome.wireBottomNav(root, app);

    try {
      const balance = await LeaveApi.balance();
      const lang = LeaveI18n.getLang();
      const detail = root.querySelector('#balance-detail');
      const monthlyRate = Number(balance.monthly_rate || 0);
      const annual = Number(balance.annual_entitlement || 0).toFixed(0);
      detail.innerHTML = `
        <p class="hint" id="balance-year-hint">
          ${esc(t('leaveYear'))}: ${esc(formatDateRange(balance.leave_year_start, balance.leave_year_end, lang))}
        </p>
        <p class="hint reset-hint">
          ${esc(t('serviceYears'))}: ${Number(balance.service_years || 0)}
          · ${esc(t('annualEntitlement'))}: ${annual} ${esc(t('daysPerYear'))}
          · ${esc(t('monthlyRate'))}: ${formatDays(monthlyRate, 2)} ${esc(t('daysPerMonth'))}
        </p>
        <p class="hint reset-hint">${esc(t('resetHint'))}</p>
        <p class="hint reset-hint">${esc(t('monthlyAccrualHint'))}</p>
        ${balance.source === 'hr_import' ? `<p class="hint reset-hint">${esc(t('hrImportHint'))}</p>` : ''}
        ${renderMonthlyTable(balance, lang, t)}
      `;
    } catch (e) {
      root.querySelector('#balance-detail').innerHTML = `<div class="error-banner show">${esc(e.message)}</div>`;
    }
  };
})();
