// ปฏิทินบันทึกการเข้าเรียน — โหลดข้อมูลรายเดือนผ่าน Ajax
(function () {
  const root = document.getElementById("calendar");
  if (!root) return;
  const MONTHS = ["มกราคม","กุมภาพันธ์","มีนาคม","เมษายน","พฤษภาคม","มิถุนายน","กรกฎาคม","สิงหาคม","กันยายน","ตุลาคม","พฤศจิกายน","ธันวาคม"];
  const DOW = ["อา","จ","อ","พ","พฤ","ศ","ส"];
  const title = document.getElementById("cal-title");
  const head = document.getElementById("cal-head");
  const body = document.getElementById("cal-body");
  head.innerHTML = DOW.map((d) => `<div class="cal-dow">${d}</div>`).join("");

  let cur = new Date(); cur = new Date(cur.getFullYear(), cur.getMonth(), 1);
  const pad = (n) => String(n).padStart(2, "0");
  const level = (s) => (s >= 1800 ? "l3" : s >= 600 ? "l2" : s > 0 ? "l1" : "");
  const label = (s) => (s >= 3600 ? Math.floor(s / 3600) + "ชม." + Math.round((s % 3600) / 60) + "น." : Math.max(1, Math.round(s / 60)) + "น.");

  async function load() {
    const y = cur.getFullYear(), m = cur.getMonth() + 1;
    title.textContent = MONTHS[m - 1] + " " + (y + 543);
    const data = await LMH.get(`${root.dataset.url}?month=${y}-${m}`);
    const first = new Date(y, m - 1, 1).getDay();
    const days = new Date(y, m, 0).getDate();
    const today = new Date();
    let html = "";
    for (let i = 0; i < first; i++) html += '<div class="cal-day empty"></div>';
    for (let d = 1; d <= days; d++) {
      const key = `${y}-${pad(m)}-${pad(d)}`;
      const secs = data.days[key] || 0;
      const isToday = today.getFullYear() === y && today.getMonth() + 1 === m && today.getDate() === d;
      html += `<div class="cal-day ${level(secs)} ${isToday ? "today" : ""}" title="${secs ? label(secs) : "ไม่ได้เรียน"}">${d}${secs ? `<small>${label(secs)}</small>` : ""}</div>`;
    }
    body.innerHTML = html;
  }
  document.getElementById("cal-prev").onclick = () => { cur = new Date(cur.getFullYear(), cur.getMonth() - 1, 1); load(); };
  document.getElementById("cal-next").onclick = () => { cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1); load(); };
  load();
})();
