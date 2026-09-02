/* global window, LeaveI18n, LeaveApi, LeaveScreens, LeavePush, LeaveSafe */
(function () {
  const app = {
    state: {
      user: null,
      isApprover: false,
      summaryTab: 'pending',
      approvalTab: 'pending',
      selectedLeave: null,
      deferredInstall: null,
    },

    toast(msg) {
      let el = document.querySelector('.toast');
      if (!el) {
        el = document.createElement('div');
        el.className = 'toast';
        document.body.appendChild(el);
      }
      el.textContent = msg;
      el.classList.add('show');
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => el.classList.remove('show'), 4500);
    },

    navigate(name) {
      const root = document.getElementById('app');
      const screen = LeaveScreens[name];
      if (!screen) {
        root.textContent = '';
        const div = document.createElement('div');
        div.className = 'loading';
        div.textContent = `Unknown screen: ${name}`;
        root.appendChild(div);
        return;
      }
      window.location.hash = name;
      const result = screen(root, this);
      if (result && typeof result.then === 'function') {
        result.catch((e) => {
          const esc = (window.LeaveSafe && LeaveSafe.escapeHtml) || ((s) => String(s || ''));
          root.innerHTML = `<div class="screen"><div class="overlap-wrap"><div class="error-banner show">${esc(e.message)}</div></div></div>`;
        });
      }
      this.renderInstallBanner();
    },

    renderInstallBanner() {
      let bar = document.getElementById('install-banner');
      const canInstall = !!(this.state.deferredInstall || this._iosInstallHint);
      const standalone =
        window.matchMedia('(display-mode: standalone)').matches ||
        window.navigator.standalone === true;
      if (standalone || !canInstall) {
        if (bar) bar.remove();
        return;
      }
      if (!bar) {
        bar = document.createElement('div');
        bar.id = 'install-banner';
        bar.className = 'install-banner';
        document.body.appendChild(bar);
      }
      const t = (k) => LeaveI18n.t(k);
      bar.innerHTML = `
        <div class="install-banner-text">
          <strong>${t('installTitle')}</strong>
          <span>${t('installHint')}</span>
        </div>
        <button type="button" class="btn-primary install-btn" id="btn-install-app">${t('installBtn')}</button>
        <button type="button" class="icon-btn ghost" id="btn-install-dismiss" aria-label="close">×</button>
      `;
      bar.querySelector('#btn-install-dismiss').addEventListener('click', () => {
        sessionStorage.setItem('leave_pwa_install_dismiss', '1');
        bar.remove();
      });
      bar.querySelector('#btn-install-app').addEventListener('click', async () => {
        if (this.state.deferredInstall) {
          this.state.deferredInstall.prompt();
          try {
            await this.state.deferredInstall.userChoice;
          } catch (e) {
            /* ignore */
          }
          this.state.deferredInstall = null;
          bar.remove();
          return;
        }
        // iOS Safari: show how-to toast
        this.toast(t('installIosHint'));
      });
      if (sessionStorage.getItem('leave_pwa_install_dismiss') === '1') {
        bar.remove();
      }
    },

    wireInstallPrompt() {
      window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        this.state.deferredInstall = e;
        this.renderInstallBanner();
      });
      const ua = navigator.userAgent || '';
      const isIOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
      const standalone = window.navigator.standalone === true;
      if (isIOS && !standalone) {
        this._iosInstallHint = true;
        this.renderInstallBanner();
      }
      window.addEventListener('appinstalled', () => {
        this.state.deferredInstall = null;
        const bar = document.getElementById('install-banner');
        if (bar) bar.remove();
        this.toast(LeaveI18n.t('installDone'));
      });
    },

    async setupNotifications() {
      if (!LeaveApi.getToken()) return;
      if (!window.isSecureContext) return;
      const sameOrigin = localStorage.getItem('leave_pwa_push_origin') === window.location.origin;
      if (localStorage.getItem('leave_pwa_push') === '1' && sameOrigin) {
        try {
          await LeavePush.enablePush(this, { silent: true });
        } catch (e) {
          /* ignore */
        }
        return;
      }
      // Soft prompt once per session after login
      if (sessionStorage.getItem('leave_pwa_push_asked') === '1') return;
      sessionStorage.setItem('leave_pwa_push_asked', '1');
      setTimeout(() => {
        if (confirm(LeaveI18n.t('pushAsk'))) {
          LeavePush.enablePush(this);
        }
      }, 1200);
    },

    async boot() {
      LeaveI18n.applyDocument();
      this.wireInstallPrompt();
      const token = LeaveApi.getToken();
      const user = LeaveApi.getUser();
      if (token && user) {
        this.state.user = user;
        this.state.isApprover = !!(user.leave_approver || (user.access && user.access.timeoff === 'manager'));
        try {
          const me = await LeaveApi.me();
          if (me) {
            this.state.isApprover = !!(me.leave_approver || (me.access && me.access.timeoff === 'manager'));
            this.state.user = Object.assign({}, user, me);
          }
        } catch (e) {
          LeaveApi.clearSession();
          this.navigate('login');
          return;
        }
        const hash = (window.location.hash || '').replace('#', '');
        const allowed = ['summary', 'balance', 'submit', 'approvals', 'approval_detail'];
        this.navigate(allowed.includes(hash) ? hash : 'summary');
        this.setupNotifications();
      } else {
        this.navigate('login');
      }

      if ('serviceWorker' in navigator) {
        const ready = window.LeavePush && LeavePush.ensureServiceWorker
          ? LeavePush.ensureServiceWorker()
          : navigator.serviceWorker.register('/leave/sw.js');
        ready.catch(() => {});
      }
    },
  };

  window.LeaveApp = app;
  document.addEventListener('DOMContentLoaded', () => app.boot());
})();
