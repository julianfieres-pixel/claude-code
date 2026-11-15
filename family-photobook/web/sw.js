// Offline support: cache the app shell and models after first visit (stale-while-revalidate).
const CACHE = 'fotojahr-v3';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return; // never cache Google/OSM calls
  e.respondWith(caches.open(CACHE).then(async cache => {
    const hit = await cache.match(e.request);
    const net = fetch(e.request).then(res => { if (res.ok) cache.put(e.request, res.clone()); return res; }).catch(() => hit);
    // app code: always the newest version when online; big libraries and models: cache first
    const fresh = e.request.mode === 'navigate' || !url.pathname.startsWith('/vendor/');
    return fresh ? (await net) || hit : hit || net;
  }));
});
