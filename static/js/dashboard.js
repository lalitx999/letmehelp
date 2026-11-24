(function () {
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
