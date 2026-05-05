const CACHE_NAME = "mago-emergency-v2";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("push", (event) => {
  if (!event.data) return;

  let data;
  try {
    data = event.data.json();
  } catch {
    data = { title: "긴급 알림", body: event.data.text(), type: "emergency" };
  }

  const isUrgent = data.type === "emergency" || data.type === "reminder" || data.type === "unacknowledged";

  const options = {
    body: data.body,
    icon: "/api/static/icon.svg",
    badge: "/api/static/icon.svg",
    vibrate: isUrgent ? [500, 200, 500, 200, 500, 200, 1000] : [200, 100, 200],
    tag: data.tag || `emergency-${Date.now()}`,
    requireInteraction: isUrgent,
    renotify: true,
    data: {
      emergencyId: data.emergencyId,
      shotCode: data.shotCode,
      projectName: data.projectName,
      type: data.type,
      url: `/api/app?emergency=${data.emergencyId}`,
    },
    actions: isUrgent
      ? [
          { action: "open", title: "즉시 확인" },
        ]
      : [],
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const { url, emergencyId } = event.notification.data || {};
  const targetUrl = url || `/api/app`;

  if (event.action === "dismiss") return;

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes("/api/app") && "focus" in client) {
          client.postMessage({ type: "EMERGENCY_CLICK", emergencyId });
          return client.focus();
        }
      }
      return clients.openWindow(targetUrl);
    })
  );
});
