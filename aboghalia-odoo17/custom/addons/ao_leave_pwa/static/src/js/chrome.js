/* global window, LeaveI18n, LeaveSafe, LeavePush */
(function () {
  const esc = (v) => (window.LeaveSafe ? LeaveSafe.escapeHtml(v) : String(v == null ? '' : v));

  function userBits(app) {
    const user = (app && app.state && app.state.user) || {};
    const name = user.employee_name || user.name || user.login || '';
    const avatar = user.avatar_base64 || '';
    const initial = (name || '?').trim().charAt(0).toUpperCase();
    return { name, avatar, initial };
  }

  function avatarHtml(user) {
    if (user.avatar) {
      return `<img class="user-avatar" src="data:image/png;base64,${user.avatar}" alt=""/>`;
    }
    return `<div class="user-avatar placeholder" aria-hidden="true">${esc(user.initial)}</div>`;
  }

  /**
   * @param {object} app
   * @param {{
   *   title: string,
   *   subtitle?: string,
   *   showBack?: boolean,
   *   showLang?: boolean,
   *   showLogout?: boolean,
   *   showNotify?: boolean,
   *   showArt?: boolean,
   * }} opts
   */
  function renderHeader(app, opts) {
    const t = (k) => LeaveI18n.t(k);
    const o = Object.assign({
      showBack: false,
      showLang: true,
      showLogout: true,
      showNotify: false,
      showArt: true,
    }, opts || {});
    const user = userBits(app);
    const navStart = o.showBack ? `
      <button class="icon-btn" id="btn-back" type="button" title="${esc(t('myLeaves'))}">
        <svg class="rtl-flip" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 6l6 6-6 6"/></svg>
      </button>
    ` : '<span class="nav-spacer" aria-hidden="true"></span>';

    const actionBits = [];
    if (o.showNotify) {
      actionBits.push(`
        <button class="icon-btn ghost" id="btn-enable-push" type="button" title="${esc(t('enableNotifications'))}">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5"/><path d="M9 17a3 3 0 0 0 6 0"/></svg>
        </button>
      `);
    }
    if (o.showLang) {
      actionBits.push(`
        <button class="icon-btn ghost" id="btn-lang" type="button" title="${esc(t('language'))}">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>
        </button>
      `);
    }
    if (o.showLogout) {
      actionBits.push(`
        <button class="logout-chip" id="btn-logout" type="button" title="${esc(t('logout'))}">
          <svg class="rtl-flip" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>
          <span>${esc(t('logout'))}</span>
        </button>
      `);
    }

    return `
      <div class="top-header">
        <div class="nav-row">
          <div class="nav-start">${navStart}</div>
          ${actionBits.length ? `<div class="nav-actions">${actionBits.join('')}</div>` : ''}
        </div>
        <div class="header-title-block">
          <h1>${esc(o.title || '')}</h1>
          ${o.subtitle ? `<p>${esc(o.subtitle)}</p>` : ''}
        </div>
        ${o.showArt ? '<img class="header-art" src="/leave/static/img/suitcase.svg" alt=""/>' : ''}
      </div>
    `;
  }

  function wireHeader(root, app, opts) {
    const o = opts || {};
    root.querySelector('#btn-logout')?.addEventListener('click', () => {
      LeaveApi.clearSession();
      app.navigate('login');
    });
    root.querySelector('#btn-lang')?.addEventListener('click', () => {
      LeaveI18n.setLang(LeaveI18n.getLang() === 'ar' ? 'en' : 'ar');
      app.navigate(o.reloadScreen || 'summary');
    });
    root.querySelector('#btn-enable-push')?.addEventListener('click', () => {
      if (window.LeavePush) LeavePush.enablePush(app);
    });
    root.querySelector('#btn-back')?.addEventListener('click', () => {
      app.navigate(o.backScreen || 'summary');
    });
  }

  function renderBottomNav(app, active) {
    const t = (k) => LeaveI18n.t(k);
    const isApprover = !!(app && app.state && app.state.isApprover);
    const items = [
      { go: 'summary', label: t('myLeaves'), active: active === 'summary' },
      { go: 'balance', label: t('monthlyBreakdown'), active: active === 'balance' },
    ];
    if (isApprover) {
      items.push({ go: 'approvals', label: t('approvals'), active: active === 'approvals' });
    }
    const colsClass = items.length === 3 ? 'cols-3' : '';
    return `
      <div class="bottom-nav ${colsClass}">
        ${items.map((item) => `
          <button type="button" class="${item.active ? 'active' : ''}" data-go="${esc(item.go)}">${esc(item.label)}</button>
        `).join('')}
      </div>
    `;
  }

  function wireBottomNav(root, app) {
    root.querySelectorAll('.bottom-nav button').forEach((el) => {
      el.addEventListener('click', () => app.navigate(el.dataset.go));
    });
  }

  window.LeaveChrome = { renderHeader, wireHeader, renderBottomNav, wireBottomNav };
})();
