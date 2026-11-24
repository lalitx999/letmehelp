// หลังบ้าน: ลากวางจัดลำดับบท/คลิป (ใช้ pointer events จึงใช้ได้ทั้งเมาส์และนิ้วบน iPad/มือถือ)
// ลากที่ปุ่ม .drag-handle ภายในรายการเดียวกัน ปล่อยแล้วบันทึกทันที · กดปุ่มแล้วใช้ลูกศร ↑ ↓ บนคีย์บอร์ดก็ได้
(function () {
  const root = document.querySelector('[data-sort="sections"]');
  if (!root) return;
  const itemsOf = (list) => [...list.children].filter((c) => c.matches("[data-sort-item]"));
  const order = (list) => itemsOf(list).map((c) => c.dataset.id);
  let drag = null;

  async function save(list, before) {
    const ids = order(list);
    if (ids.join() === before) return;
    const url = document.querySelector('[data-sort="sections"]').dataset.sortUrl;
    const body = list.dataset.sort === "sections" ? { kind: "sections", ids } : { kind: "lessons", parent: list.dataset.parent, ids };
    const res = await LMH.post(url, body);
    if (res.ok && res.data.ok !== false) return window.LMHDash.done(res.data.message || "จัดลำดับแล้ว");
    LMH.toast((res.data && res.data.error) || "บันทึกลำดับไม่สำเร็จ", "bad");
    window.LMHDash.refresh(); // คืนลำดับตามที่บันทึกไว้จริง
  }

  document.addEventListener("pointerdown", (e) => {
    const h = e.target.closest(".drag-handle");
    if (!h || h.classList.contains("is-demo") || e.button > 0) return;
    const item = h.closest("[data-sort-item]");
    const list = item && item.parentElement;
    if (!list || !list.matches("[data-sort]")) return;
    e.preventDefault();
    h.setPointerCapture(e.pointerId);
    drag = { item, list, before: order(list) .join() };
    item.classList.add("is-dragging");
    document.body.classList.add("is-sorting");
  });

  document.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const others = itemsOf(drag.list).filter((c) => c !== drag.item);
    const target = others.find((c) => { const r = c.getBoundingClientRect(); return e.clientY < r.top + r.height / 2; });
    if (target) { if (drag.item.nextElementSibling !== target) drag.list.insertBefore(drag.item, target); }
    else if (others.length) others[others.length - 1].after(drag.item);
    if (e.clientY < 70) window.scrollBy(0, -14);
    else if (e.clientY > window.innerHeight - 70) window.scrollBy(0, 14);
  });

  function end() {
    if (!drag) return;
    const d = drag;
    drag = null;
    d.item.classList.remove("is-dragging");
    document.body.classList.remove("is-sorting");
    save(d.list, d.before);
  }
  document.addEventListener("pointerup", end);
  document.addEventListener("pointercancel", end);

  // คีย์บอร์ด: โฟกัสที่ปุ่มลาก แล้วกด ↑ ↓
  document.addEventListener("keydown", (e) => {
    const h = e.target.closest && e.target.closest(".drag-handle");
    if (!h || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    const item = h.closest("[data-sort-item]"), list = item.parentElement;
    const before = order(list).join();
    const sib = e.key === "ArrowUp" ? item.previousElementSibling : item.nextElementSibling;
    if (!sib || !sib.matches("[data-sort-item]")) return;
    e.preventDefault();
    if (e.key === "ArrowUp") sib.before(item); else sib.after(item);
    h.focus();
    save(list, before);
  });
})();
