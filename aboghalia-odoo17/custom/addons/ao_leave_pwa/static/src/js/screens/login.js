/* global window, LeaveI18n, LeaveApi */
(function () {
  function iconEnvelope() {
    return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16v12H4z"/><path d="m4 7 8 6 8-6"/></svg>`;
  }
  function iconLock() {
    return `<span style="font-weight:800;letter-spacing:1px">***</span>`;
  }
  function iconEye() {
    return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3l18 18"/><path d="M10.6 10.6a2 2 0 0 0 2.8 2.8"/><path d="M9.9 5.1A9.8 9.8 0 0 1 12 5c5 0 9.3 3.1 11 7-0.6 1.4-1.5 2.7-2.6 3.7"/><path d="M6.1 6.1C4.2 7.4 2.7 9.1 1.5 12c1.7 3.9 6 7 10.5 7 1.4 0 2.8-.3 4-.8"/></svg>`;
  }
  function iconGlobe() {
    return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>`;
  }

  window.LeaveScreens = window.LeaveScreens || {};
  window.LeaveScreens.login = function (root, app) {
    const t = (k) => LeaveI18n.t(k);
    const saved = LeaveApi.getSavedEmails();
    root.innerHTML = `
      <div class="login-screen">
        <div class="login-hero">
          <div class="login-brand">SJC<span class="star">✦</span></div>
          <div class="login-company">${t('companyName')}</div>
        </div>
        <div class="login-card">
          <h1>${t('loginTitle')}</h1>
          <p class="subtitle">${t('loginSubtitle')}</p>
          <div class="error-banner" id="login-error"></div>
          <div class="field">
            <div class="field-box">
              <span class="icon">${iconEnvelope()}</span>
              <input id="login-email" type="email" autocomplete="username" placeholder="${t('email')}" list="saved-emails" value="${(window.LeaveSafe ? LeaveSafe.escapeAttr(saved[0] || '') : (saved[0] || ''))}"/>
              <datalist id="saved-emails">${saved.map((e) => `<option value="${window.LeaveSafe ? LeaveSafe.escapeAttr(e) : e}">`).join('')}</datalist>
            </div>
          </div>
          <div class="field">
            <div class="field-box">
              <span class="icon">${iconLock()}</span>
              <input id="login-password" type="password" autocomplete="current-password" placeholder="${t('password')}"/>
              <button type="button" class="trailing" id="toggle-pass" aria-label="toggle">${iconEye()}</button>
            </div>
          </div>
          <div class="login-row">
            <label><input type="checkbox" id="remember-me" checked/> ${t('rememberMe')}</label>
            <button type="button" class="link-btn" id="clear-emails">${t('clearEmails')}</button>
          </div>
          <button class="btn-primary" id="login-submit">
            <span>${t('loginBtn')}</span>
            <span aria-hidden="true">${LeaveI18n.getLang() === 'ar' ? '←' : '→'}</span>
          </button>
          <button class="btn-outline" id="toggle-lang">${iconGlobe()} ${t('changeLang')}</button>
        </div>
      </div>
    `;

    root.querySelector('#toggle-pass').addEventListener('click', () => {
      const input = root.querySelector('#login-password');
      input.type = input.type === 'password' ? 'text' : 'password';
    });

    root.querySelector('#clear-emails').addEventListener('click', () => {
      LeaveApi.clearSavedEmails();
      app.toast(t('clearEmails'));
      app.navigate('login');
    });

    root.querySelector('#toggle-lang').addEventListener('click', () => {
      const next = LeaveI18n.getLang() === 'ar' ? 'en' : 'ar';
      LeaveI18n.setLang(next);
      app.navigate('login');
    });

    const submit = async () => {
      const email = root.querySelector('#login-email').value.trim();
      const password = root.querySelector('#login-password').value;
      const remember = root.querySelector('#remember-me').checked;
      const errEl = root.querySelector('#login-error');
      errEl.classList.remove('show');
      if (!email || !password) {
        errEl.textContent = t('required');
        errEl.classList.add('show');
        return;
      }
      const btn = root.querySelector('#login-submit');
      btn.disabled = true;
      try {
        const data = await LeaveApi.login(email, password);
        data.login = email;
        LeaveApi.setSession(data, remember);
        app.state.user = data;
        app.state.isApprover = !!(data.leave_approver || (data.access && data.access.timeoff === 'manager'));
        app.navigate('summary');
        if (app.setupNotifications) app.setupNotifications();
      } catch (e) {
        errEl.textContent = e.message || t('loginFailed');
        errEl.classList.add('show');
      } finally {
        btn.disabled = false;
      }
    };

    root.querySelector('#login-submit').addEventListener('click', submit);
    root.querySelector('#login-password').addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') submit();
    });
  };
})();
