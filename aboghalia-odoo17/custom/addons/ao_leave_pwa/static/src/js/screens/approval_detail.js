/* global window, LeaveI18n, LeaveApi, LeaveSafe, LeaveChrome */
(function () {
  const esc = (v) => (window.LeaveSafe ? LeaveSafe.escapeHtml(v) : String(v == null ? '' : v));

  window.LeaveScreens = window.LeaveScreens || {};
  window.LeaveScreens.approval_detail = function (root, app) {
    const t = (k) => LeaveI18n.t(k);
    const item = app.state.selectedLeave;
    if (!item) {
      app.navigate('approvals');
      return;
    }
    const canDecide = !!item.can_decide && item.state === 'confirm';
    const waitingLabel = item.waiting_for || item.current_level_label || LeaveI18n.levelLabel(item.current_level);
    root.innerHTML = `
      <div class="screen no-fab">
        ${LeaveChrome.renderHeader(app, {
          title: t('details'),
          subtitle: item.employee_name || '',
          showBack: true,
          showLang: false,
          showLogout: false,
        })}
        <div class="overlap-wrap">
          <div class="card">
            <div class="error-banner" id="detail-error"></div>
            <div class="detail-rows">
              <div class="detail-row"><span class="lbl">${esc(t('employee'))}</span><span class="val">${esc(item.employee_name || '—')}</span></div>
              <div class="detail-row"><span class="lbl">${esc(t('leaveType'))}</span><span class="val">${esc(item.holiday_type || '—')}</span></div>
              <div class="detail-row"><span class="lbl">${esc(t('from'))}</span><span class="val">${esc(item.request_date_from || '—')}</span></div>
              <div class="detail-row"><span class="lbl">${esc(t('to'))}</span><span class="val">${esc(item.request_date_to || '—')}</span></div>
              <div class="detail-row"><span class="lbl">${esc(t('days'))}</span><span class="val">${Number(item.number_of_days || 0).toFixed(1)} ${esc(t('days'))}</span></div>
              <div class="detail-row"><span class="lbl">${esc(t('waitingFor'))}</span><span class="val">${esc(item.state === 'validate' ? t('fullyDone') : (waitingLabel || '—'))}</span></div>
              <div class="detail-row"><span class="lbl">${esc(t('reason'))}</span><span class="val">${esc(item.name || '—')}</span></div>
              ${item.balance_warning ? `
                <div class="detail-row balance-warning-row">
                  <span class="lbl">${esc(t('approverBalanceNote'))}</span>
                  <span class="val balance-warning-flag">${esc(item.balance_warning)}</span>
                </div>
              ` : ''}
              ${item.company_name ? `<div class="detail-row"><span class="lbl">${esc(t('company'))}</span><span class="val">${esc(item.company_name)}</span></div>` : ''}
            </div>
            ${canDecide ? `
              <div class="action-row" style="margin-top:18px">
                <button class="btn-refuse" id="btn-refuse">${esc(t('refuse'))}</button>
                <button class="btn-approve" id="btn-approve">${esc(t('approve'))}</button>
              </div>
            ` : ''}
          </div>
        </div>
      </div>
    `;

    LeaveChrome.wireHeader(root, app, { backScreen: 'approvals' });

    const setBusy = (busy) => {
      root.querySelector('#btn-approve') && (root.querySelector('#btn-approve').disabled = busy);
      root.querySelector('#btn-refuse') && (root.querySelector('#btn-refuse').disabled = busy);
    };

    root.querySelector('#btn-approve')?.addEventListener('click', async () => {
      const err = root.querySelector('#detail-error');
      err.classList.remove('show');
      err.textContent = '';
      setBusy(true);
      try {
        const res = await LeaveApi.approve(item.id);
        err.classList.remove('show');
        err.textContent = '';
        app.toast((res && res.message) || t('approvedOk'));
        app.state.approvalTab = 'approved';
        app.navigate('approvals');
      } catch (e) {
        // If backend finished the leave but still returned noise, refresh list quietly
        err.textContent = e.message;
        err.classList.add('show');
        setBusy(false);
      }
    });

    root.querySelector('#btn-refuse')?.addEventListener('click', async () => {
      const err = root.querySelector('#detail-error');
      err.classList.remove('show');
      setBusy(true);
      try {
        await LeaveApi.refuse(item.id);
        app.toast(t('refusedOk'));
        app.navigate('approvals');
      } catch (e) {
        err.textContent = e.message;
        err.classList.add('show');
        setBusy(false);
      }
    });
  };
})();
