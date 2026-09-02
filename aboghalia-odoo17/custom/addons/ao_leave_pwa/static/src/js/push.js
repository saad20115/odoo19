/* global window, LeaveApi, LeaveI18n */
(function () {
  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
    return out;
  }

  function isIos() {
    const ua = navigator.userAgent || '';
    return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  }

  function isStandalone() {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true
    );
  }

  function notify(app, silent, msg) {
    if (silent) return;
    if (app && typeof app.toast === 'function') {
      app.toast(msg);
    } else {
      window.alert(msg);
    }
  }

  async function ensureServiceWorker() {
    if (!('serviceWorker' in navigator)) return null;
    // Important: do NOT unregister + await ready — that hangs forever on iOS WebKit.
    // pushManager works on the registration object without controlling the page.
    return navigator.serviceWorker.register('/leave/sw.js');
  }

  async function enablePush(app, options) {
    const opts = options || {};
    const silent = !!opts.silent;
    const t = (k) => LeaveI18n.t(k);

    if (!window.isSecureContext) {
      notify(app, silent, t('pushNeedsHttps'));
      return false;
    }
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      notify(app, silent, t('pushUnsupported'));
      return false;
    }
    if (isIos() && !isStandalone()) {
      notify(app, silent, t('pushIosInstallFirst'));
      return false;
    }

    try {
      const reg = await ensureServiceWorker();
      if (!reg || !reg.pushManager) {
        notify(app, silent, t('pushUnavailable'));
        return false;
      }
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        notify(app, silent, t('pushDenied'));
        return false;
      }
      const vapid = await LeaveApi.pushVapid();
      if (!vapid || !vapid.publicKey) {
        notify(app, silent, t('pushUnavailable'));
        return false;
      }
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapid.publicKey),
        });
      }
      await LeaveApi.pushSubscribe(sub.toJSON());
      localStorage.setItem('leave_pwa_push', '1');
      localStorage.setItem('leave_pwa_push_origin', window.location.origin);
      notify(app, silent, t('pushEnabled'));
      return true;
    } catch (e) {
      notify(app, silent, (e && e.message) || t('pushUnavailable'));
      return false;
    }
  }

  window.LeavePush = { enablePush, ensureServiceWorker, isIos, isStandalone };
})();
