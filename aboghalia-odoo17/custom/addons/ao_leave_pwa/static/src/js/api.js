/* global window */
(function () {
  const TOKEN_KEY = 'leave_pwa_token';
  const USER_KEY = 'leave_pwa_user';
  const COMPANY_KEY = 'leave_pwa_company';
  const REMEMBER_KEY = 'leave_pwa_remember';
  const SAVED_EMAILS_KEY = 'leave_pwa_saved_emails';

  function extractErrorMessage(body, res) {
    if (!body || typeof body !== 'object') return '';
    const candidates = [
      body.message,
      body.error,
      body.description,
      body.data && body.data.message,
    ];
    for (const item of candidates) {
      if (typeof item === 'string' && item.trim()) {
        return item.trim();
      }
    }
    if (body.type && window.LeaveI18n) {
      const key = `apiError_${body.type}`;
      const translated = LeaveI18n.t(key);
      if (translated && translated !== key) {
        return translated;
      }
    }
    if (res && res.status === 400 && window.LeaveI18n) {
      return LeaveI18n.t('apiError_generic');
    }
    return (res && res.statusText) || 'Request failed';
  }

  async function parseResponse(res) {
    let body = null;
    const text = await res.text();
    try {
      body = text ? JSON.parse(text) : null;
    } catch (e) {
      body = null;
    }
    if (!res.ok) {
      const msg = extractErrorMessage(body, res);
      const err = new Error(msg);
      err.status = res.status;
      err.body = body;
      err.type = body && body.type;
      throw err;
    }
    return body;
  }

  function unwrap(body) {
    if (!body) return body;
    if (Object.prototype.hasOwnProperty.call(body, 'data')) {
      return body.data;
    }
    return body;
  }

  window.LeaveApi = {
    formatError(err) {
      if (!err) return (window.LeaveI18n && LeaveI18n.t('apiError_generic')) || 'Request failed';
      if (err.body && typeof err.body.message === 'string' && err.body.message.trim()) {
        return err.body.message.trim();
      }
      if (err.message && err.message !== 'Bad Request') {
        return err.message;
      }
      if (err.type && window.LeaveI18n) {
        const key = `apiError_${err.type}`;
        const translated = LeaveI18n.t(key);
        if (translated && translated !== key) return translated;
      }
      return (window.LeaveI18n && LeaveI18n.t('apiError_generic')) || 'Request failed';
    },
    getToken() {
      return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
    },
    getUser() {
      const raw = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);
      try {
        return raw ? JSON.parse(raw) : null;
      } catch (e) {
        return null;
      }
    },
    getCompanyId() {
      return localStorage.getItem(COMPANY_KEY) || sessionStorage.getItem(COMPANY_KEY);
    },
    setSession(userPayload, remember) {
      localStorage.setItem(REMEMBER_KEY, remember ? '1' : '0');
      const store = remember ? localStorage : sessionStorage;
      (remember ? sessionStorage : localStorage).removeItem(TOKEN_KEY);
      (remember ? sessionStorage : localStorage).removeItem(USER_KEY);
      (remember ? sessionStorage : localStorage).removeItem(COMPANY_KEY);

      store.setItem(TOKEN_KEY, userPayload.access_token);
      store.setItem(USER_KEY, JSON.stringify(userPayload));
      if (userPayload.default_company_id) {
        store.setItem(COMPANY_KEY, String(userPayload.default_company_id));
      }
      if (remember && userPayload.login) {
        this.saveEmail(userPayload.login);
      }
    },
    clearSession() {
      [localStorage, sessionStorage].forEach((s) => {
        s.removeItem(TOKEN_KEY);
        s.removeItem(USER_KEY);
        s.removeItem(COMPANY_KEY);
      });
    },
    saveEmail(email) {
      const list = this.getSavedEmails().filter((e) => e !== email);
      list.unshift(email);
      localStorage.setItem(SAVED_EMAILS_KEY, JSON.stringify(list.slice(0, 8)));
    },
    getSavedEmails() {
      try {
        return JSON.parse(localStorage.getItem(SAVED_EMAILS_KEY) || '[]');
      } catch (e) {
        return [];
      }
    },
    clearSavedEmails() {
      localStorage.removeItem(SAVED_EMAILS_KEY);
    },
    headers(json = true) {
      const h = {};
      if (json) h['Content-Type'] = 'application/json';
      const token = this.getToken();
      if (token) h['access-token'] = token;
      const company = this.getCompanyId();
      if (company) {
        h['x-company-id'] = company;
        h['x-company-ids'] = company;
      }
      try {
        h['Accept-Language'] = (window.LeaveI18n && LeaveI18n.getLang()) || 'ar';
      } catch (e) {
        h['Accept-Language'] = 'ar';
      }
      return h;
    },
    async login(login, password) {
      const res = await fetch('/leave/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login, password }),
      });
      return parseResponse(res);
    },
    async me() {
      const res = await fetch('/leave/api/me', { headers: this.headers(false) });
      return unwrap(await parseResponse(res));
    },
    async balance() {
      const res = await fetch('/leave/api/employee/balance', { headers: this.headers(false) });
      return unwrap(await parseResponse(res));
    },
    async types() {
      const res = await fetch('/leave/api/employee/types', { headers: this.headers(false) });
      return unwrap(await parseResponse(res));
    },
    async myRequests(kind) {
      const map = {
        pending: '/leave/api/employee/requests/pending',
        approved: '/leave/api/employee/requests/approved',
        refused: '/leave/api/employee/requests/refused',
      };
      const res = await fetch(map[kind] || map.pending, { headers: this.headers(false) });
      return unwrap(await parseResponse(res)) || [];
    },
    async createLeave(payload) {
      const res = await fetch('/leave/api/employee/create', {
        method: 'POST',
        headers: this.headers(true),
        body: JSON.stringify(payload),
      });
      return unwrap(await parseResponse(res));
    },
    async managerRequests(kind) {
      const map = {
        pending: '/leave/api/manager/timeoff/requests/pending',
        approved: '/leave/api/manager/timeoff/requests/approved',
        refused: '/leave/api/manager/timeoff/requests/refused',
      };
      const res = await fetch((map[kind] || map.pending) + '?limit=50', {
        headers: this.headers(false),
      });
      const data = unwrap(await parseResponse(res));
      if (data && Array.isArray(data.data)) return data.data;
      if (Array.isArray(data)) return data;
      return [];
    },
    async pendingCount() {
      const res = await fetch('/leave/api/manager/pending_count', { headers: this.headers(false) });
      const data = unwrap(await parseResponse(res));
      return (data && (data.count || data.data?.count)) || 0;
    },
    async approve(requestId) {
      const res = await fetch('/leave/api/manager/timeoff/approve', {
        method: 'POST',
        headers: this.headers(true),
        body: JSON.stringify({ request_id: requestId }),
      });
      return unwrap(await parseResponse(res));
    },
    async refuse(requestId) {
      const res = await fetch('/leave/api/manager/timeoff/refuse', {
        method: 'POST',
        headers: this.headers(true),
        body: JSON.stringify({ request_id: requestId }),
      });
      return unwrap(await parseResponse(res));
    },
    async pushVapid() {
      const res = await fetch('/leave/api/push/vapid', { headers: this.headers(false) });
      return unwrap(await parseResponse(res));
    },
    async pushSubscribe(subscription) {
      const res = await fetch('/leave/api/push/subscribe', {
        method: 'POST',
        headers: this.headers(true),
        body: JSON.stringify({ subscription }),
      });
      return unwrap(await parseResponse(res));
    },
    async pushUnsubscribe(endpoint) {
      const res = await fetch('/leave/api/push/unsubscribe', {
        method: 'POST',
        headers: this.headers(true),
        body: JSON.stringify({ endpoint }),
      });
      return unwrap(await parseResponse(res));
    },
  };
})();
