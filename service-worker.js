const CACHE_NAME = 'learnnest-cache-v1';
const STATIC_ASSETS = [
  '/',
  '/static/style.css',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  // Add more static files as needed
];
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  if (event.request.destination === 'document') {
    // Network first for HTML
    event.respondWith(
      fetch(event.request).then(response => {
        const resClone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, resClone));
        return response;
      }).catch(() => caches.match(event.request))
    );
  } else {
    // Cache first for static
    event.respondWith(
      caches.match(event.request).then(res => res || fetch(event.request))
    );
  }
});
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    ))
  );
}); 