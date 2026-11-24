{% load static %}
// Service worker แบบเบา: cache ไฟล์ static + หน้า offline เท่านั้น (ไม่ cache หน้าที่มีข้อมูลผู้ใช้/วิดีโอ)
const CACHE = "lmh-static-v5";
const PRECACHE = ["{% url 'core:offline' %}", "{% static 'css/site.css' %}", "{% static 'vendor/bootstrap/css/bootstrap.min.css' %}", "{% static 'img/logo.png' %}", "{% static 'vendor/bootstrap-icons/icons.svg' %}", "{% static 'js/site.js' %}"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith("/static/")) {
    // network-first: ได้ไฟล์ล่าสุดเสมอ ถ้าออฟไลน์ค่อยใช้ของที่ cache ไว้
    e.respondWith(fetch(req, { cache: "no-cache" }).then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res; }).catch(() => caches.match(req)));
    return;
  }
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => caches.match("{% url 'core:offline' %}")));
  }
});
