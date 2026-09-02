/* global window, LeaveI18n, LeaveApi, LeaveSafe, LeaveChrome */
(function () {
  const esc = (v) => (window.LeaveSafe ? LeaveSafe.escapeHtml(v) : String(v == null ? '' : v));

  function estimateDays(from, to) {
    if (!from || !to) return 0;
    const start = new Date(`${from}T12:00:00`);
    const end = new Date(`${to}T12:00:00`);
    if (end < start) return 0;
    return Math.round((end - start) / 86400000) + 1;
  }

  function isPaidType(types, typeId) {
    const row = (types || []).find((ty) => String(ty.id || ty.holiday_status_id) === String(typeId));
    if (!row) return true;
    if (row.key === 'unpaid') return false;
    if (row.key === 'paid') return true;
    return !row.unpaid;
  }

  function normalizeTypes(raw) {
    let list = raw;
    if (list && list.types) list = list.types;
    if (list && list.data) list = list.data;
    if (!Array.isArray(list)) return [];
    const keyed = list.filter((ty) => ty.key === 'paid' || ty.key === 'unpaid');
    if (keyed.length) return keyed;
    return list.slice(0, 2);
  }

  function buildWarning(t, remaining, requested) {
    if (remaining <= 0) {
      return t('noRemainingDays');
    }
    if (requested > 0 && requested > remaining) {
      return t('insufficientDays')
        .replace('{requested}', Number(requested).toFixed(1))
        .replace('{remaining}', Number(remaining).toFixed(1));
    }
    return '';
  }

  window.LeaveScreens = window.LeaveScreens || {};
  window.LeaveScreens.submit = async function (root, app) {
    const t = (k) => LeaveI18n.t(k);
    root.innerHTML = `
      <div class="screen no-fab">
        ${LeaveChrome.renderHeader(app, {
          title: t('submitLeave'),
          subtitle: t('appTitle'),
          showBack: true,
          showLogout: false,
        })}
        <div class="overlap-wrap">
          <div class="card">
            <div class="error-banner" id="form-error"></div>
            <div class="warning-banner" id="form-warning"></div>
            <p class="balance-hint" id="balance-hint">
              ${esc(t('availableBalance'))}: <strong id="balance-value">—</strong> ${esc(t('days'))}
              <br/><span class="hint">${esc(t('approvedOnlyHint'))}</span>
            </p>
            <div class="form-group">
              <label>${t('leaveType')}</label>
              <select id="leave-type"><option value="">...</option></select>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>${t('from')}</label>
                <input type="date" id="date-from"/>
              </div>
              <div class="form-group">
                <label>${t('to')}</label>
                <input type="date" id="date-to"/>
              </div>
            </div>
            <div class="form-group">
              <label>${t('reason')}</label>
              <textarea id="leave-reason" placeholder="${t('reason')}"></textarea>
            </div>
            <button class="btn-primary" id="btn-create">${t('submit')}</button>
          </div>
        </div>
      </div>
    `;

    let types = [];
    let balance = null;

    const warningEl = root.querySelector('#form-warning');
    const balanceValueEl = root.querySelector('#balance-value');

    const refreshWarning = () => {
      const holiday_status_id = root.querySelector('#leave-type').value;
      const request_date_from = root.querySelector('#date-from').value;
      const request_date_to = root.querySelector('#date-to').value;
      warningEl.classList.remove('show');
      warningEl.textContent = '';
      if (!holiday_status_id || !isPaidType(types, holiday_status_id) || !balance) {
        return;
      }
      const remaining = Number(balance.all_remaining || 0);
      const requested = estimateDays(request_date_from, request_date_to);
      const msg = buildWarning(t, remaining, requested);
      if (msg) {
        warningEl.textContent = msg;
        warningEl.classList.add('show');
      }
    };

    LeaveChrome.wireHeader(root, app, { reloadScreen: 'submit', backScreen: 'summary' });
    ['#leave-type', '#date-from', '#date-to'].forEach((sel) => {
      root.querySelector(sel).addEventListener('change', refreshWarning);
      root.querySelector(sel).addEventListener('input', refreshWarning);
    });

    try {
      const [typesRes, balanceRes] = await Promise.all([
        LeaveApi.types().catch(() => []),
        LeaveApi.balance().catch(() => null),
      ]);
      types = normalizeTypes(typesRes);
      balance = balanceRes;
      if (balanceValueEl && balance) {
        const remaining = Math.max(0, Number(balance.all_remaining || 0));
        balanceValueEl.textContent = remaining.toFixed(1);
      }
      const sel = root.querySelector('#leave-type');
      sel.innerHTML = `<option value="">${esc(t('leaveType'))}</option>` + types.map((ty) => {
        const id = Number(ty.id || ty.holiday_status_id) || '';
        let name = ty.name || ty.display_name || ty.holiday_type || `#${id}`;
        if (ty.key === 'paid') name = t('leavePaid');
        else if (ty.key === 'unpaid') name = t('leaveUnpaid');
        return `<option value="${id}" data-key="${esc(ty.key || '')}">${esc(name)}</option>`;
      }).join('');
      refreshWarning();
    } catch (e) {
      root.querySelector('#form-error').textContent = e.message;
      root.querySelector('#form-error').classList.add('show');
    }

    root.querySelector('#btn-create').addEventListener('click', async () => {
      const err = root.querySelector('#form-error');
      err.classList.remove('show');
      const holiday_status_id = root.querySelector('#leave-type').value;
      const request_date_from = root.querySelector('#date-from').value;
      const request_date_to = root.querySelector('#date-to').value;
      const name = root.querySelector('#leave-reason').value.trim() || 'Time Off Request';
      if (!holiday_status_id || !request_date_from || !request_date_to) {
        err.textContent = t('required');
        err.classList.add('show');
        return;
      }
      refreshWarning();
      const btn = root.querySelector('#btn-create');
      btn.disabled = true;
      try {
        const payload = {
          holiday_status_id: Number(holiday_status_id),
          request_date_from,
          request_date_to,
          name,
          request_unit_half: false,
        };
        await LeaveApi.createLeave(payload);
        app.toast(t('created'));
        app.state.summaryTab = 'pending';
        app.navigate('summary');
      } catch (e) {
        err.textContent = LeaveApi.formatError(e);
        err.classList.add('show');
      } finally {
        btn.disabled = false;
      }
    });
  };
})();
