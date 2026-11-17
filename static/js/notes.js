// สมุดโน้ตส่วนตัวในหน้าเรียน: บันทึกอัตโนมัติ (Ajax), แทรกเวลา [mm:ss], คลิกเวลาเพื่อข้ามวิดีโอ, คัดลอก, ดาวน์โหลด .txt
(function () {
  const pane = document.getElementById("tab-notes");
  if (!pane) return;
  const url = pane.dataset.noteUrl;
  const area = document.getElementById("note-text");
  const status = document.getElementById("note-status");
  const stamps = document.getElementById("note-stamps");
  let timer = null;
  let loaded = false;

  const fmt = (s) => String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
  const toSec = (t) => { const [m, s] = t.split(":").map(Number); return m * 60 + s; };
  const say = (t) => { status.textContent = t; };

  function renderStamps() {
    const found = [...new Set(area.value.match(/\[\d{1,3}:\d{2}\]/g) || [])];
    stamps.innerHTML = "";
    found.forEach((tag) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip is-blue border-0";
      b.innerHTML = LMH.icon("play-fill") + " " + tag.slice(1, -1);
      b.addEventListener("click", () => window.LMHPlayer && window.LMHPlayer.seek(toSec(tag.slice(1, -1))));
      stamps.appendChild(b);
    });
  }

  async function save() {
    say("กำลังบันทึก…");
    const res = await LMH.post(url, { content: area.value });
    say(res.ok ? "บันทึกแล้ว " + (res.data.updated_at || "") : "บันทึกไม่สำเร็จ");
  }

  area.addEventListener("input", () => {
    if (!loaded) return;
    renderStamps();
    say("กำลังพิมพ์…");
    clearTimeout(timer);
    timer = setTimeout(save, 1000);
  });

  document.getElementById("note-stamp").addEventListener("click", () => {
    const t = window.LMHPlayer ? window.LMHPlayer.time() : 0;
    const tag = "[" + fmt(t) + "] ";
    const pos = area.selectionStart ?? area.value.length;
    area.value = area.value.slice(0, pos) + tag + area.value.slice(pos);
    area.focus();
    area.selectionStart = area.selectionEnd = pos + tag.length;
    area.dispatchEvent(new Event("input"));
  });

  document.getElementById("note-copy").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(area.value); LMH.toast("คัดลอกโน้ตแล้ว", "ok"); }
    catch (e) { area.select(); LMH.toast("เลือกข้อความแล้ว กด Ctrl+C เพื่อคัดลอก", "info"); }
  });

  document.getElementById("note-download").addEventListener("click", () => {
    const blob = new Blob([pane.dataset.noteTitle + "\n\n" + area.value], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "note-" + pane.dataset.noteTitle.replace(/[^\w฀-๿-]+/g, "_") + ".txt";
    a.click();
    URL.revokeObjectURL(a.href);
  });

  window.addEventListener("pagehide", () => {
    if (loaded && timer) { clearTimeout(timer); fetch(url, { method: "POST", keepalive: true, credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": LMH.cookie("csrftoken") }, body: JSON.stringify({ content: area.value }) }); }
  });

  LMH.get(url).then((d) => { area.value = d.content || ""; loaded = true; renderStamps(); });
})();
