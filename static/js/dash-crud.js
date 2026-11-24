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

  // ทำรายการเสร็จ: ดึงหน้าเดิมมาใหม่แล้วเปลี่ยนเฉพาะเนื้อหา (ไม่รีโหลดทั้งหน้า ตำแหน่งที่เลื่อนอยู่ไม่หาย)
  // เมนูข้าง (ตัวเลขสลิปรอตรวจ) อัปเดตด้วย และถ้าแผงรายละเอียดเปิดอยู่ก็โหลดแผงใหม่
  const SWAP = ["main.adm-content", ".adm-side .adm-nav", "#dashDrawer .adm-nav"];
  async function refresh() {
    const res = await fetch(location.href, { credentials: "same-origin" });
    if (!res.ok || res.redirected) throw new Error("reload");
    const doc = new DOMParser().parseFromString(await res.text(), "text/html");
    SWAP.forEach((sel) => { const now = document.querySelector(sel), next = doc.querySelector(sel); if (now && next) now.innerHTML = next.innerHTML; });
    document.dispatchEvent(new CustomEvent("dash:refreshed"));
  }
  const done = async (message, kind) => {
    try {
      await refresh();
      if (panelEl.classList.contains("show") && panelUrl) await loadPanel(panelUrl);
      LMH.toast(message || "ทำรายการแล้ว", kind || "ok");
    } catch (e) {
      try { sessionStorage.setItem("lmh-flash", JSON.stringify({ message, kind: kind || "ok" })); } catch (err) { /* ไม่เป็นไร */ }
      location.reload();
    }
  };

  // แผงรายละเอียดด้านขวา: <button data-panel-url="...">
  const panelEl = document.getElementById("dashPanel");
  const panel = new bootstrap.Offcanvas(panelEl);
  const panelBody = panelEl.querySelector(".dash-panel-body");
  let panelUrl = "";
  async function loadPanel(url) {
    panelUrl = url;
    const res = await fetch(url, { headers: FETCH, credentials: "same-origin" });
    panelBody.innerHTML = await res.text();
  }
  async function openPanel(url) {
    panelBody.innerHTML = '<div class="p-5 text-center"><span class="spinner-border" aria-hidden="true"></span></div>';
    panel.show();
    try { await loadPanel(url); } catch (e) { panel.hide(); LMH.toast("โหลดข้อมูลไม่สำเร็จ", "bad"); }
  }

  async function openModal(url, size) {
    const dialog = crudEl.querySelector(".modal-dialog");
    dialog.classList.toggle("modal-lg", size === "lg");
    dialog.classList.toggle("modal-xl", size === "xl");
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
    if (m) { e.preventDefault(); if (m.closest("#dashPanel")) panel.hide(); return openModal(m.dataset.modalUrl, m.dataset.modalSize); }

    const pn = e.target.closest("[data-panel-url]");
    if (pn) { e.preventDefault(); return openPanel(pn.dataset.panelUrl); }

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

  // ปฏิเสธสลิป: ถามเหตุผล (นักเรียนจะเห็นข้อความนี้) แล้วส่งไป server
  document.addEventListener("click", async (e) => {
    const b = e.target.closest(".js-reject");
    if (!b) return;
    const reason = prompt("เหตุผลที่ปฏิเสธ (นักเรียนจะเห็นข้อความนี้)", "สลิปไม่ถูกต้อง");
    if (reason === null) return;
    b.disabled = true;
    const res = await LMH.post(b.dataset.url, { action: "reject", reason });
    if (res.ok && res.data.ok !== false) return done(res.data.message || "ปฏิเสธสลิปแล้ว");
    b.disabled = false;
    LMH.toast((res.data && res.data.error) || "ทำรายการไม่สำเร็จ", "bad");
  });

  // หน้าต่างนักเรียน: ปุ่มลัด +30 วัน / +1 ปี / ตลอดชีพ และสวิตช์เปิดสิทธิ์
  const ymd = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  function setRowOn(row, on) {
    row.classList.toggle("is-on", on);
    const t = row.querySelector("[data-access-toggle]"), date = row.querySelector("[data-access-date]");
    t.checked = on;
    if (on && !date.value) date.value = ymd(addDays(new Date(), parseInt(date.dataset.defaultDays, 10) || 365));
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-add-days]");
    if (!b) return;
    const row = b.closest("[data-access-row]"), date = row.querySelector("[data-access-date]");
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const cur = date.value ? new Date(date.value + "T00:00") : null;
    const base = cur && cur > today ? cur : today;
    date.value = ymd(b.dataset.addDays === "lifetime" ? addDays(today, 36500) : addDays(base, parseInt(b.dataset.addDays, 10)));
    setRowOn(row, true);
  });
  document.addEventListener("change", (e) => {
    if (e.target.matches("[data-access-toggle]")) setRowOn(e.target.closest("[data-access-row]"), e.target.checked);
  });

  // ให้สคริปต์ของแต่ละหน้าใช้: แจ้งผล+อัปเดตหน้า, เปิด modal/แผง
  window.LMHDash = { done, refresh, openModal, openPanel, confirm: confirmThen };

  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      const s = document.querySelector("[data-search]");
      if (s) { e.preventDefault(); s.focus(); }
    }
  });

  // ปุ่มค้นหาในแถบบน: โฟกัสช่องค้นหาของหน้า (ซ่อนปุ่มถ้าหน้านั้นไม่มีช่องค้นหา)
  const searchBtn = document.querySelector("[data-focus-search]");
  if (searchBtn) {
    const syncSearch = () => { searchBtn.hidden = !document.querySelector("[data-search]"); };
    syncSearch();
    document.addEventListener("dash:refreshed", syncSearch);
    searchBtn.addEventListener("click", () => { const s = document.querySelector("[data-search]"); if (s) { s.scrollIntoView({ block: "center", behavior: "smooth" }); s.focus({ preventScroll: true }); } });
  }
})();
