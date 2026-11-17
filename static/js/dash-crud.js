// หลังบ้าน: ฟอร์ม modal (Ajax), ปุ่มลัด POST (ลบ/กู้คืน/สลับ/เลื่อนลำดับ), bulk, แจ้งผลด้วย toast, ปุ่ม "/" ไปช่องค้นหา
(function () {
  const crudEl = document.getElementById("crudModal");
  const confirmEl = document.getElementById("confirmModal");
  if (!crudEl) return;
  const crud = new bootstrap.Modal(crudEl);
  const confirmModal = new bootstrap.Modal(confirmEl);
  const content = crudEl.querySelector(".modal-content");
  const FETCH = { "X-Requested-With": "fetch" };

  // แสดง toast ที่ค้างไว้ข้ามการรีโหลดหน้า
  try {
    const flash = sessionStorage.getItem("lmh-flash");
    if (flash) { sessionStorage.removeItem("lmh-flash"); const f = JSON.parse(flash); LMH.toast(f.message, f.kind); }
  } catch (e) { /* ไม่เป็นไร */ }

  const done = (message, kind) => {
    try { sessionStorage.setItem("lmh-flash", JSON.stringify({ message, kind: kind || "ok" })); } catch (e) { /* ไม่เป็นไร */ }
    location.reload();
  };

  async function openModal(url) {
    content.innerHTML = '<div class="p-5 text-center"><span class="spinner-border" aria-hidden="true"></span></div>';
    crud.show();
    try {
      const res = await fetch(url, { headers: FETCH, credentials: "same-origin" });
      content.innerHTML = await res.text();
      const first = content.querySelector("input:not([type=hidden]), select, textarea");
      if (first) setTimeout(() => first.focus(), 250);
    } catch (e) { crud.hide(); LMH.toast("โหลดฟอร์มไม่สำเร็จ", "bad"); }
  }

  function confirmThen(text, danger, fn) {
    document.getElementById("confirmText").textContent = text || "";
    const ok = document.getElementById("confirmOk");
    ok.className = "btn " + (danger ? "btn-outline-danger" : "btn-dark");
    const handler = async () => { ok.removeEventListener("click", handler); ok.disabled = true; try { await fn(); } finally { ok.disabled = false; confirmModal.hide(); } };
    ok.addEventListener("click", handler);
    confirmEl.addEventListener("hidden.bs.modal", () => ok.removeEventListener("click", handler), { once: true });
    confirmModal.show();
  }

  async function postJson(url, data) {
    const res = await LMH.post(url, data || {});
    if (res.ok && res.data.ok !== false) return done(res.data.message || "ทำรายการแล้ว");
    LMH.toast((res.data && res.data.error) || "ทำรายการไม่สำเร็จ", "bad");
  }

  document.addEventListener("click", (e) => {
    const m = e.target.closest("[data-modal-url]");
    if (m) { e.preventDefault(); return openModal(m.dataset.modalUrl); }

    const p = e.target.closest("[data-post-url]");
    if (p) {
      e.preventDefault();
      const send = () => postJson(p.dataset.postUrl, p.dataset.payload ? JSON.parse(p.dataset.payload) : {});
      // data-confirm2 = ยืนยันซ้ำอีกชั้น (ใช้กับการลบถาวร): ปิดกล่องแรกก่อนแล้วเปิดกล่องที่สองด้วยข้อความใหม่
      const run = p.dataset.confirm2
        ? () => new Promise((resolve) => {
            confirmEl.addEventListener("hidden.bs.modal", () => { confirmThen(p.dataset.confirm2, true, send); }, { once: true });
            resolve();
          })
        : send;
      if (p.dataset.confirm) confirmThen(p.dataset.confirm, p.dataset.danger !== undefined, run);
      else run();
      return;
    }

    const b = e.target.closest("[data-bulk-action]");
    if (b) {
      const ids = [...document.querySelectorAll("[data-bulk-id]:checked")].map((c) => c.dataset.bulkId);
      if (!ids.length) return LMH.toast("เลือกรายการก่อน", "info");
      const run = () => postJson(b.dataset.bulkUrl, { ids, action: b.dataset.bulkAction });
      if (b.dataset.confirm) confirmThen(b.dataset.confirm.replace("{n}", ids.length), b.dataset.danger !== undefined, run);
      else run();
    }
  });

  // ส่งฟอร์มใน modal แบบ Ajax (รองรับอัปโหลดไฟล์)
  content.addEventListener("submit", async (e) => {
    const form = e.target.closest("form[data-modal-form]");
    if (!form) return;
    e.preventDefault();
    const btn = form.querySelector("button:not([type=button])");
    if (btn) btn.disabled = true;
    const res = await fetch(form.action, { method: "POST", body: new FormData(form), headers: { ...FETCH, "X-CSRFToken": LMH.cookie("csrftoken") }, credentials: "same-origin" });
    const type = res.headers.get("content-type") || "";
    if (type.includes("json")) { const d = await res.json(); if (d.ok) { crud.hide(); return done(d.message); } LMH.toast(d.error || "ไม่สำเร็จ", "bad"); }
    else content.innerHTML = await res.text(); // ฟอร์มพร้อมข้อความผิดพลาด
  });

  // bulk: เลือกทั้งหมด + แถบจำนวนที่เลือก
  const bar = document.getElementById("bulkBar");
  const sync = () => {
    const n = document.querySelectorAll("[data-bulk-id]:checked").length;
    if (bar) { bar.hidden = n === 0; const c = bar.querySelector("[data-bulk-count]"); if (c) c.textContent = n; }
  };
  document.addEventListener("change", (e) => {
    if (e.target.matches("[data-bulk-all]")) document.querySelectorAll("[data-bulk-id]").forEach((c) => (c.checked = e.target.checked));
    if (e.target.matches("[data-bulk-all], [data-bulk-id]")) sync();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      const s = document.querySelector("[data-search]");
      if (s) { e.preventDefault(); s.focus(); }
    }
  });
})();
