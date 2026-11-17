// helper กลาง: Ajax (fetch + CSRF), ไอคอน, toast, reveal เมื่อเลื่อนถึง, สลับแสดงรหัสผ่าน
window.LMH = (function () {
  function cookie(name) {
    const m = document.cookie.match("(?:^|; )" + name + "=([^;]*)");
    return m ? decodeURIComponent(m[1]) : "";
  }
  async function post(url, data, isForm) {
    const opts = { method: "POST", headers: { "X-CSRFToken": cookie("csrftoken") }, credentials: "same-origin" };
    if (isForm) opts.body = data;
    else { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(data); }
    const res = await fetch(url, opts);
    let json = {};
    try { json = await res.json(); } catch (e) { /* ไม่ใช่ JSON */ }
    return { ok: res.ok, status: res.status, data: json };
  }
  async function get(url) {
    const res = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    return res.json();
  }
  // <svg><use> จาก sprite — URL ของ sprite ส่งมากับ <body data-icons>
  function icon(name, cls) {
    const base = document.body.dataset.icons || "";
    return `<svg class="icon ${cls || ""}" aria-hidden="true"><use href="${base}#${name}"/></svg>`;
  }
  function toast(message, kind) {
    let host = document.getElementById("toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "toast-host";
      host.className = "toast-container position-fixed top-0 end-0 p-3";
      host.style.zIndex = 2000;
      document.body.appendChild(host);
    }
    const ic = { ok: "check-circle-fill", bad: "x-circle-fill", info: "info-circle" }[kind || "info"];
    const col = { ok: "#1c7c4a", bad: "#b3261e", info: "#054f90" }[kind || "info"];
    const el = document.createElement("div");
    el.className = "toast align-items-center";
    el.setAttribute("role", "status");
    el.innerHTML = `<div class="d-flex"><div class="toast-body d-flex gap-2 align-items-start"><span style="color:${col}">${icon(ic, "icon-lg")}</span><span></span></div><button type="button" class="btn-close me-3 m-auto" data-bs-dismiss="toast" aria-label="ปิด"></button></div>`;
    el.querySelector(".toast-body span:last-child").textContent = message;
    host.appendChild(el);
    const t = new bootstrap.Toast(el, { delay: 5000 });
    el.addEventListener("hidden.bs.toast", () => el.remove());
    t.show();
  }
  return { post, get, cookie, icon, toast };
})();

// reveal เมื่อเลื่อนถึง (ข้ามถ้าผู้ใช้ตั้งค่าลดแอนิเมชัน)
(function () {
  const els = document.querySelectorAll("[data-reveal]");
  if (!els.length) return;
  if (!("IntersectionObserver" in window) || matchMedia("(prefers-reduced-motion: reduce)").matches) {
    els.forEach((e) => e.classList.add("is-in"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); } });
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
  els.forEach((e) => io.observe(e));
})();

// เมนูเต็มจอ (มือถือ/แท็บเล็ต) + เงาใต้ navbar เมื่อเลื่อน + นาฬิกาไทยบนหน้าแรก
(function () {
  const btn = document.getElementById("menuBtn");
  const overlay = document.getElementById("menuOverlay");
  const nav = document.getElementById("siteNav");
  if (nav) {
    const onScroll = () => nav.classList.toggle("is-scrolled", window.scrollY > 8);
    onScroll(); window.addEventListener("scroll", onScroll, { passive: true });
  }
  if (btn && overlay) {
    const set = (open) => {
      overlay.classList.toggle("is-open", open);
      overlay.setAttribute("aria-hidden", String(!open));
      btn.setAttribute("aria-expanded", String(open));
      document.body.classList.toggle("menu-open", open);
    };
    btn.addEventListener("click", () => set(btn.getAttribute("aria-expanded") !== "true"));
    overlay.addEventListener("click", (e) => { if (e.target.closest("a")) set(false); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") set(false); });
    window.matchMedia("(min-width: 992px)").addEventListener("change", (e) => { if (e.matches) set(false); });
  }
  document.querySelectorAll("[data-clock]").forEach((el) => {
    const tick = () => {
      const t = new Intl.DateTimeFormat("th-TH", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Bangkok" }).format(new Date());
      el.textContent = "( " + t + " TH )";
    };
    tick(); setInterval(tick, 20000);
  });
})();

// ปุ่มแสดง/ซ่อนรหัสผ่าน
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-pw-toggle]");
  if (!btn) return;
  const input = document.querySelector(btn.dataset.pwToggle);
  if (!input) return;
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  btn.innerHTML = LMH.icon(show ? "eye-slash" : "eye");
  btn.setAttribute("aria-label", show ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน");
});

// PWA: ลงทะเบียน service worker
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

// PWA: ปุ่ม "ติดตั้งแอป" (Android/Chrome/Edge ใช้ beforeinstallprompt · iPhone ต้องติดตั้งเองจากปุ่มแชร์ จึงแสดงคำแนะนำ)
(function () {
  const btns = () => document.querySelectorAll("[data-pwa-install]");
  const hints = () => document.querySelectorAll("[data-pwa-ios]");
  const standalone = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  if (standalone()) return;
  let deferred = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferred = e;
    btns().forEach((b) => (b.hidden = false));
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    btns().forEach((b) => (b.hidden = true));
    hints().forEach((h) => (h.hidden = true));
    LMH.toast("ติดตั้งแอปเรียบร้อยแล้ว", "ok");
  });
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
  document.addEventListener("DOMContentLoaded", () => { if (ios) btns().forEach((b) => (b.hidden = false)); });
  document.addEventListener("click", async (e) => {
    if (!e.target.closest("[data-pwa-install]")) return;
    if (deferred) {
      deferred.prompt();
      await deferred.userChoice.catch(() => {});
      deferred = null;
      btns().forEach((b) => (b.hidden = true));
    } else if (ios) {
      hints().forEach((h) => (h.hidden = !h.hidden));
    }
  });
})();
