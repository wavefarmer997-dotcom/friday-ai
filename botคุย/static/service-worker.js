/**
 * Friday PWA Service Worker
 * แคชไฟล์พื้นฐานเพื่อการเปิดแอปที่รวดเร็วและรองรับออฟไลน์เชลล์
 */

const CACHE_NAME = "friday-cache-v2.5";
const ASSETS_TO_CACHE = [
  "/",
  "/static/manifest.json",
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png"
];

// Install Event
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log("[ServiceWorker] Caching App Shell");
      return cache.addAll(ASSETS_TO_CACHE);
    }).then(() => self.skipWaiting())
  );
});

// Activate Event (Clear Old Caches)
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(
        keyList.map((key) => {
          if (key !== CACHE_NAME) {
            console.log("[ServiceWorker] Removing old cache", key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event (Network First with Cache Fallback for dynamic app)
self.addEventListener("fetch", (event) => {
  // ไม่แคชคำขอ WebSocket, API Streaming, หรือ External AI
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/ws/") || url.pathname.startsWith("/api/")) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // หากโหลดสำเร็จ บันทึกสำเนาลงแคช
        if (response.status === 200) {
          const resClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, resClone);
          });
        }
        return response;
      })
      .catch(() => {
        // หากไม่มีเน็ต ให้ดึงจากแคช
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) return cachedResponse;
          if (event.request.headers.get("accept").includes("text/html")) {
            return caches.match("/");
          }
        });
      })
  );
});
