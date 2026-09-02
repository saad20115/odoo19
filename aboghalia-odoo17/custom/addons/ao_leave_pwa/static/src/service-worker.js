/* SJC Leaves PWA — offline shell + push */
const CACHE = 'ao-leave-pwa-v17';
const ASSETS = [
  '/leave',
  '/leave/static/img/icon.svg',
  '/leave/static/img/icon-192.png',
  '/leave/static/img/icon-512.png',
  '/leave/static/img/suitcase.svg',
  '/leave/static/img/suitcase-empty.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/leave/api/')) {
    return;
  }
  if (event.request.method !== 'GET') {
    return;
  }
  // Always fetch fresh JS/CSS/HTML so balance + leave-type fixes reach phones.
  if (
    url.pathname.startsWith('/leave/static/js/')
    || url.pathname.startsWith('/leave/static/css/')
    || url.pathname === '/leave'
    || url.pathname === '/leave/'
  ) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request)
        .then((res) => {
          if (res && res.ok && url.origin === self.location.origin) {
            const clone = res.clone();
            caches.open(CACHE).then((cache) => cache.put(event.request, clone));
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});

self.addEventListener('push', (event) => {
  let payload = { title: 'SJC Leaves', body: '', data: {}, url: '/leave' };
  try {
    if (event.data) {
      const parsed = event.data.json();
      payload = Object.assign(payload, parsed || {});
    }
  } catch (e) {
    try {
      payload.body = event.data ? event.data.text() : '';
    } catch (e2) {
      /* ignore */
    }
  }
  const title = payload.title || 'SJC Leaves';
  const options = {
    body: payload.body || '',
    icon: '/leave/static/img/icon-192.png',
    badge: '/leave/static/img/icon-192.png',
    data: Object.assign({ url: payload.url || '/leave' }, payload.data || {}),
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/leave';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ('focus' in client) {
          client.navigate(target);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(target);
      }
      return undefined;
    })
  );
});
