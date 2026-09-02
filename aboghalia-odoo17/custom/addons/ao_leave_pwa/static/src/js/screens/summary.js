/* global window, LeaveI18n, LeaveApi, LeaveSafe, LeavePush, LeaveChrome */
(function () {
  const esc = (v) => (window.LeaveSafe ? LeaveSafe.escapeHtml(v) : String(v == null ? '' : v));

  function formatPeriod(lang) {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    const opts = { day: 'numeric', month: 'long', year: 'numeric' };
    const locale = lang === 'ar' ? 'ar-EG' : 'en-GB';
    return `${start.toLocaleDateString(locale, opts)} - ${end.toLocaleDateString(locale, opts)}`;
  }

  function formatDateRange(fromIso, toIso, lang) {
    if (!fromIso || !toIso) return '—';
    const opts = { day: 'numeric', month: 'short', year: 'numeric' };
    const locale = lang === 'ar' ? 'ar-EG' : 'en-GB';
    const from = new Date(`${fromIso}T12:00:00`);
    const to = new Date(`${toIso}T12:00:00`);
    return `${from.toLocaleDateString(locale, opts)} - ${to.toLocaleDateString(locale, opts)}`;
  }

  function sumBalance(balance) {
    let available = 0;
    let used = 0;
    if (!balance) return { available, used, stale: false };
    if (balance.source === 'saudi_labor_law') {
      return {
        available: Math.max(0, Number(balance.all_remaining || 0)),
        used: Number(balance.all_spent || 0),
        stale: false,
      };
    }
    if (typeof balance.all_remaining === 'number') {
      return {
        available: Math.max(0, Number(balance.all_remaining || 0)),
        used: Number(balance.all_spent || 0),
        stale: false,
      };
    }
    if (typeof balance.grand_total_remaining === 'number') {
      return {
        available: Math.max(0, Number(balance.grand_total_remaining || 0)),
        used: Number(balance.grand_total_spent || 0),
        stale: true,
      };
    }
    const list = balance.balances || balance.types || (Array.isArray(balance) ? balance : []);
    if (Array.isArray(list)) {
      list.forEach((row) => {
        available += Number(row.remaining_days || row.remaining || 0);
        used += Number(row.total_spent || row.spent || 0);
      });
      return { available: Math.max(0, available), used, stale: true };
    }
    return { available, used, stale: false };
  }

  function chipClass(tab) {
    if (tab === 'approved') return 'approved';
    if (tab === 'refused') return 'refused';
    return 'pending';
  }

  window.LeaveScreens = window.LeaveScreens || {};
  window.LeaveScreens.summary = async function (root, app) {
    const t = (k) => LeaveI18n.t(k);
    const tab = app.state.summaryTab || 'pending';
    root.innerHTML = `
      <div class="screen ${app.state.isApprover ? 'with-nav with-nav-fab' : 'with-nav'}">
        ${LeaveChrome.renderHeader(app, {
          title: t('leaveSummary'),
          subtitle: t('submitLeave'),
          showNotify: true,
        })}
        <div class="overlap-wrap">
          <div class="card" id="balance-card">
            <h2>${esc(t('totalLeaves'))}</h2>
            <p class="hint" id="balance-period-hint">${esc(t('period'))} ${esc(formatPeriod(LeaveI18n.getLang()))}</p>
            <p class="hint approved-only-hint">${esc(t('approvedOnlyHint'))}</p>
            <p class="hint" id="balance-monthly-hint"></p>
            <div class="stats-row">
              <div class="stat-box">
                <div class="stat-label"><span class="dot green"></span>${esc(t('available'))}</div>
                <div class="stat-value" id="stat-available">—</div>
              </div>
              <div class="stat-box">
                <div class="stat-label"><span class="dot purple"></span>${esc(t('used'))}</div>
                <div class="stat-value" id="stat-used">—</div>
              </div>
            </div>
          </div>
          <div class="tabs">
            <button class="tab ${tab === 'refused' ? 'active' : ''}" data-tab="refused">${esc(t('refused'))} <span class="badge" id="c-refused">0</span></button>
            <button class="tab ${tab === 'approved' ? 'active' : ''}" data-tab="approved">${esc(t('approved'))} <span class="badge" id="c-approved">0</span></button>
            <button class="tab ${tab === 'pending' ? 'active' : ''}" data-tab="pending">${esc(t('pending'))} <span class="badge" id="c-pending">0</span></button>
          </div>
          <div class="card list-card" id="list-area">
            <div class="loading">${esc(t('loading'))}</div>
          </div>
          <button type="button" class="btn-outline notify-btn" id="btn-enable-push">${esc(t('enableNotifications'))}</button>
        </div>
        ${app.state.isApprover ? `
          ${LeaveChrome.renderBottomNav(app, 'summary')}
        ` : `
          ${LeaveChrome.renderBottomNav(app, 'summary')}
          <div class="fab-bar fab-bar-above-nav">
            <button class="btn-primary" id="btn-submit">${esc(t('submitLeave'))}</button>
          </div>
        `}
      </div>
    `;

    if (app.state.isApprover) {
      const fab = document.createElement('div');
      fab.className = 'fab-bar fab-bar-above-nav';
      fab.innerHTML = `<button class="btn-primary" id="btn-submit">${esc(t('submitLeave'))}</button>`;
      root.querySelector('.screen').appendChild(fab);
    }

    const wireChrome = () => {
      LeaveChrome.wireHeader(root, app, { reloadScreen: 'summary' });
      root.querySelector('#btn-submit')?.addEventListener('click', () => app.navigate('submit'));
      root.querySelectorAll('.tab').forEach((el) => {
        el.addEventListener('click', () => {
          app.state.summaryTab = el.dataset.tab;
          app.navigate('summary');
        });
      });
      LeaveChrome.wireBottomNav(root, app);
    };
    wireChrome();

    try {
      const [balance, pending, approved, refused] = await Promise.all([
        LeaveApi.balance().catch(() => null),
        LeaveApi.myRequests('pending'),
        LeaveApi.myRequests('approved'),
        LeaveApi.myRequests('refused'),
      ]);
      const sums = sumBalance(balance);
      root.querySelector('#stat-available').textContent = Number(sums.available).toFixed(1);
      root.querySelector('#stat-used').textContent = Number(sums.used).toFixed(1);
      const monthlyHint = root.querySelector('#balance-monthly-hint');
      if (monthlyHint && balance && balance.monthly_rate) {
        monthlyHint.textContent = `${t('monthlyRate')}: ${Number(balance.monthly_rate).toFixed(2)} ${t('daysPerMonth')}`;
      }
      if (sums.stale) {
        const hint = root.querySelector('#balance-period-hint');
        if (hint) {
          hint.textContent = t('upgradeRequired');
          hint.classList.add('error-text');
        }
      }
      const periodHint = root.querySelector('#balance-period-hint');
      if (periodHint && balance && balance.leave_year_start) {
        const lang = LeaveI18n.getLang();
        periodHint.textContent = `${t('leaveYear')}: ${formatDateRange(balance.leave_year_start, balance.leave_year_end, lang)}`;
      }
      root.querySelector('#c-pending').textContent = pending.length;
      root.querySelector('#c-approved').textContent = approved.length;
      root.querySelector('#c-refused').textContent = refused.length;

      const lists = { pending, approved, refused };
      const items = lists[tab] || [];
      const listEl = root.querySelector('#list-area');
      if (!items.length) {
        listEl.innerHTML = `
          <h2>${esc(t('workPeriod'))}</h2>
          <p class="hint">${esc(t('workPeriodHint'))}</p>
          <div class="empty-state">
            <img src="/leave/static/img/suitcase-empty.svg" alt=""/>
            <h3>${esc(t('emptyTitle'))}</h3>
            <p>${esc(t('emptyHint'))}</p>
          </div>
        `;
      } else {
        listEl.innerHTML = `
          <h2>${esc(t('workPeriod'))}</h2>
          <p class="hint">${esc(t('workPeriodHint'))}</p>
          <div class="leave-list-grid">
          ${items.map((item) => {
            let waitHtml = '';
            if (item.state === 'confirm' && (item.waiting_for || item.current_level_label || item.current_level)) {
              const label = item.waiting_for || item.current_level_label || LeaveI18n.levelLabel(item.current_level);
              waitHtml = `<span class="waiting-pill">${esc(t('waitingFor'))}: ${esc(label)}</span>`;
            } else if (item.state === 'validate') {
              waitHtml = `<span class="waiting-pill done">${esc(t('fullyDone'))}</span>`;
            }
            return `
            <div class="leave-item" data-id="${Number(item.id) || 0}">
              <div class="leave-item-top">
                <strong>${esc(item.holiday_type || '—')}</strong>
                <span class="chip ${chipClass(tab)}">${esc(tab === 'pending' ? t('pending') : tab === 'approved' ? t('approved') : t('refused'))}</span>
              </div>
              <div class="leave-meta">
                <span>${esc(t('from'))} ${esc(item.request_date_from || '—')}</span>
                <span>${esc(t('to'))} ${esc(item.request_date_to || '—')}</span>
                <span>${Number(item.number_of_days || 0).toFixed(1)} ${esc(t('days'))}</span>
              </div>
              ${waitHtml}
              ${item.balance_warning ? `<span class="balance-warning-flag">${esc(item.balance_warning)}</span>` : ''}
            </div>`;
          }).join('')}
          </div>
        `;
      }
    } catch (e) {
      root.querySelector('#list-area').innerHTML = `<div class="error-banner show">${esc(e.message)}</div>`;
    }
  };
})();
