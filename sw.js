const CACHE = 'gfc-demo-v301';
const ASSETS = [
  '/german-flashcards-demo/manifest.json',
  '/german-flashcards-demo/icon.svg'
];

// Install: cache only non-HTML assets
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

// Activate: remove old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: HTML always from network (so updates are instant), cache everything else
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  const isHtml = url.pathname.endsWith('/') || url.pathname.endsWith('.html') || url.pathname === '/german-flashcards-demo';
  if (isHtml) {
    // Network-first for HTML — fall back to cache if offline
    e.respondWith(
      fetch(e.request).then(response => {
        const clone = response.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return response;
      }).catch(() => caches.match(e.request))
    );
    return;
  }
  // Cache-first for other assets (JSON files etc)
  e.respondWith(
    caches.open(CACHE).then(async cache => {
      const cached = await cache.match(e.request);
      const networkFetch = fetch(e.request).then(response => {
        if (response && response.status === 200) cache.put(e.request, response.clone());
        return response;
      }).catch(() => null);
      return cached || networkFetch;
    })
  );
});
