const CACHE_NAME = 'video-cache-v1';
const VIDEO_URLS = [
  '/static/videos/milkyWay.mp4',
  '/static/videos/jupiter.mp4',
  '/static/videos/crabNebula.mp4',
  '/static/videos/n11.mp4'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(VIDEO_URLS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  try {
    const reqUrl = new URL(event.request.url);
    // Only intercept requests for our video files
    if (VIDEO_URLS.includes(reqUrl.pathname)) {
      event.respondWith(
        caches.match(event.request).then((cached) => {
          if (cached) return cached;
          return fetch(event.request).then((networkResp) => {
            // cache a clone for future
            const copy = networkResp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
            return networkResp;
          }).catch(() => cached || new Response('', { status: 503 }));
        })
      );
    }
  } catch (e) {
    // ignore errors parsing URL
  }
});
