(function () {
  // ปฏิเสธสลิป: ถามเหตุผล (นักเรียนจะเห็นข้อความนี้) แล้วส่งไป server
  document.addEventListener("click", async (e) => {
    const b = e.target.closest(".js-reject");
    if (!b) return;
    const reason = prompt("เหตุผลที่ปฏิเสธ (นักเรียนจะเห็นข้อความนี้)", "สลิปไม่ถูกต้อง");
    if (reason === null) return;
    b.disabled = true;
    const res = await LMH.post(b.dataset.url, { action: "reject", reason });
    if (res.ok && res.data.ok !== false) {
      try { sessionStorage.setItem("lmh-flash", JSON.stringify({ message: res.data.message || "ปฏิเสธสลิปแล้ว", kind: "ok" })); } catch (err) { /* ไม่เป็นไร */ }
      location.reload();
    } else { b.disabled = false; LMH.toast((res.data && res.data.error) || "ทำรายการไม่สำเร็จ", "bad"); }
  });

  // รายงาน: poll สถานะงานที่กำลังสร้าง
  const table = document.getElementById("export-table");
  if (table) {
    const pending = () => [...table.querySelectorAll('tr[data-status="pending"]')];
    if (!pending().length) return;
    const timer = setInterval(async () => {
      const rows = pending();
      if (!rows.length) { clearInterval(timer); return; }
      const data = await LMH.get(table.dataset.statusUrl + "?ids=" + rows.map((r) => r.dataset.id).join(","));
      data.items.forEach((it) => {
        if (it.status === "pending") return;
        const row = table.querySelector(`tr[data-id="${it.id}"]`);
        row.dataset.status = it.status;
        if (it.status === "done") {
          row.querySelector(".js-status").innerHTML = `<span class="chip is-green">${LMH.icon("check-circle-fill")} เสร็จแล้ว</span>`;
          row.querySelector(".js-action").innerHTML = `<a class="btn btn-sm btn-dark" href="${location.pathname}${it.id}/download/">${LMH.icon("download")} ดาวน์โหลด</a>`;
          LMH.toast("รายงานพร้อมดาวน์โหลดแล้ว", "ok");
        } else {
          row.querySelector(".js-status").innerHTML = `<span class="chip is-red">${LMH.icon("x-circle-fill")} ล้มเหลว</span> <span class="small text-secondary"></span>`;
          row.querySelector(".js-status .small").textContent = it.error || "";
        }
      });
    }, 2500);
  }
})();
