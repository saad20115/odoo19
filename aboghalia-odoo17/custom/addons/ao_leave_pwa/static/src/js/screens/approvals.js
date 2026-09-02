/* global window, LeaveI18n, LeaveApi, LeaveSafe, LeaveChrome */
(function () {
  const esc = (v) => (window.LeaveSafe ? LeaveSafe.escapeHtml(v) : String(v == null ? '' : v));

  window.LeaveScreens = window.LeaveScreens || {};
  window.LeaveScreens.approvals = async function (root, app) {
    const t = (k) => LeaveI18n.t(k);
    const tab = app.state.approvalTab || 'pending';
    root.innerHTML = `
    <div class="screen with-nav">
      ${LeaveChrome.renderHeader(app, {
        title: t('approvals'),
        subtitle: t('pendingApprovals'),
        showBack: true,
      })}
        <div class="overlap-wrap">
          <div class="tabs">
            <button class="tab ${tab === 'refused' ? 'active' : ''}" data-tab="refused">${esc(t('refused'))} <span class="badge" id="c-refused">0</span></button>
            <button class="tab ${tab === 'approved' ? 'active' : ''}" data-tab="approved">${esc(t('approved'))} <span class="badge" id="c-approved">0</span></button>
            <button class="tab ${tab === 'pending' ? 'active' : ''}" data-tab="pending">${esc(t('pending'))} <span class="badge" id="c-pending">0</span></button>
          </div>
          <div class="card list-card" id="list-area">
            <div class="loading">${esc(t('loading'))}</div>
          </div>
        </div>
        ${LeaveChrome.renderBottomNav(app, 'approvals')}
      </div>
    `;

    LeaveChrome.wireHeader(root, app, { reloadScreen: 'approvals', backScreen: 'summary' });
    root.querySelectorAll('.tab').forEach((el) => {
      el.addEventListener('click', () => {
        app.state.approvalTab = el.dataset.tab;
        app.navigate('approvals');
      });
    });
    LeaveChrome.wireBottomNav(root, app);

    try {
      const [pending, approved, refused] = await Promise.all([
        LeaveApi.managerRequests('pending'),
        LeaveApi.managerRequests('approved'),
        LeaveApi.managerRequests('refused'),
      ]);
      root.querySelector('#c-pending').textContent = pending.length;
      root.querySelector('#c-approved').textContent = approved.length;
      root.querySelector('#c-refused').textContent = refused.length;
      const lists = { pending, approved, refused };
      const items = lists[tab] || [];
      const listEl = root.querySelector('#list-area');
      if (!items.length) {
        listEl.innerHTML = `
          <div class="empty-state">
            <img src="/leave/static/img/suitcase-empty.svg" alt=""/>
            <h3>${esc(t('noPending'))}</h3>
          </div>
        `;
        return;
      }
      const chip = tab === 'approved' ? 'approved' : tab === 'refused' ? 'refused' : 'pending';
      const chipLabel = tab === 'approved' ? t('approved') : tab === 'refused' ? t('refused') : t('pending');
      const waitingLine = (item) => {
        if (item.state === 'validate' || item.current_level === 'done') {
          return `<span class="waiting-pill done">${esc(t('fullyDone'))}</span>`;
        }
        if (item.state === 'confirm' && (item.waiting_for || item.current_level_label)) {
          const label = item.waiting_for || item.current_level_label || LeaveI18n.levelLabel(item.current_level);
          const prefix = tab === 'approved' ? t('forwardedTo') : t('waitingFor');
          return `<span class="waiting-pill">${esc(prefix)}: ${esc(label)}</span>`;
        }
        return '';
      };
      listEl.innerHTML = `
        <div class="leave-list-grid">
        ${items.map((item) => `
        <div class="leave-item" data-id="${Number(item.id) || 0}">
          <div class="leave-item-top">
            <strong>${esc(item.employee_name || '—')} · ${esc(item.holiday_type || '')}</strong>
            <span class="chip ${chip}">${esc(chipLabel)}</span>
          </div>
          <div class="leave-meta">
            <span>${esc(item.request_date_from || '—')} → ${esc(item.request_date_to || '—')}</span>
            <span>${Number(item.number_of_days || 0).toFixed(1)} ${esc(t('days'))}</span>
          </div>
          ${waitingLine(item)}
          ${item.balance_warning ? `<span class="balance-warning-flag">${esc(item.balance_warning)}</span>` : ''}
        </div>
      `).join('')}
        </div>
      `;

      listEl.querySelectorAll('.leave-item').forEach((el) => {
        el.addEventListener('click', () => {
          const id = Number(el.dataset.id);
          app.state.selectedLeave = items.find((i) => i.id === id);
          app.navigate('approval_detail');
        });
      });
    } catch (e) {
      root.querySelector('#list-area').innerHTML = `<div class="error-banner show">${esc(e.message)}</div>`;
    }
  };
})();
