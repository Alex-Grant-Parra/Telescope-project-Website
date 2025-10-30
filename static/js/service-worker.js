// Runtime caching for videos: don't pre-cache large files during install to avoid blocking
const CACHE_NAME = 'video-cache-v1';
const VIDEO_PATHS = ['/static/videos/'];
const MAX_VIDEO_ITEMS = 1; // only keep one video cached at a time to limit disk usage

self.addEventListener('install', (event) => {
  // Skip caching large assets on install; this keeps install quick
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Helper to check if a request is for a video in our static/videos dir
function isVideoRequest(requestUrl) {
  try {
    const p = new URL(requestUrl).pathname;
    return VIDEO_PATHS.some(prefix => p.startsWith(prefix));
  } catch (e) {
    return false;
  }
}

// On fetch: network-first for videos, but cache successful responses. Evict older entries to keep cache small.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (!isVideoRequest(req.url)) return;

  event.respondWith(
    fetch(req).then(networkResp => {
      // Clone & store in cache but keep cache small
      const clone = networkResp.clone();
      caches.open(CACHE_NAME).then(async cache => {
        try {
          await cache.put(req, clone);
          // Evict if too many video entries
          const keys = await cache.keys();
          if (keys.length > MAX_VIDEO_ITEMS) {
            // remove oldest (first) entries until within limit
            for (let i = 0; i < keys.length - MAX_VIDEO_ITEMS; i++) {
              await cache.delete(keys[i]);
            }
          }
        } catch (e) {
          // ignore caching errors
        }
      });
      return networkResp;
    }).catch(() => {
      // network failed - try cache
      return caches.match(req).then(cached => cached || new Response('', { status: 503 }));
    })
  );
});
