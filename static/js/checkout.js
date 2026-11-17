(function () {
  const box = document.getElementById("pay-box");
  if (!box) return;
  const input = document.getElementById("slip-input");
  const zone = document.getElementById("drop-zone");
  const label = document.getElementById("drop-label");
  const btn = document.getElementById("submit-slip");
  const msg = document.getElementById("pay-msg");
  const steps = document.querySelectorAll("#stepper .s");
  const btnHtml = btn.innerHTML;
  let file = null;
  let timer = null;

  const state = (kind, icon, html) => {
    msg.innerHTML = html ? `<div class="state ${kind}">${LMH.icon(icon)}<div>${html}</div></div>` : "";
  };
  const spinner = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>';
  const setStep = (n, doneAll) => steps.forEach((s) => {
    const i = +s.dataset.step;
    s.classList.toggle("done", i < n || (doneAll && i <= n));
    s.classList.toggle("on", i === n && !doneAll);
  });

  function pick(f) {
    if (!f) return;
    file = f;
    label.textContent = f.name;
    zone.classList.add("has-file");
    btn.disabled = false;
    state("", "", "");
  }
  input.addEventListener("change", () => pick(input.files[0]));
  ["dragover", "dragenter"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("drag"); }));
  zone.addEventListener("drop", (e) => pick(e.dataTransfer.files[0]));

  function lock(on) { btn.disabled = on; input.disabled = on; }

  async function poll() {
    try {
      const s = await LMH.get(box.dataset.statusUrl);
      if (s.order_status === "paid") {
        clearInterval(timer);
        setStep(3, true);
        state("ok", "check-circle-fill", "<b>ชำระเงินสำเร็จ</b> กำลังพาไปหน้า Dashboard");
        btn.innerHTML = btnHtml;
        setTimeout(() => (location.href = s.learn_url), 1400);
      } else if (s.order_status === "rejected") {
        clearInterval(timer);
        setStep(2);
        lock(false);
        btn.innerHTML = LMH.icon("upload") + " ส่งสลิปใหม่";
        state("bad", "x-circle-fill", "<b>สลิปไม่ผ่าน</b> " + (s.reason ? "— " + s.reason : "") + " กรุณาอัปโหลดใหม่");
      } else if (s.slip_status === "manual_review") {
        clearInterval(timer);
        setStep(3);
        btn.innerHTML = btnHtml;
        state("info", "hourglass-split", "<b>ได้รับสลิปแล้ว</b> ผู้ดูแลกำลังตรวจสอบ เมื่ออนุมัติจะเปิดสิทธิ์เรียนให้และแจ้งทางอีเมล");
      } else {
        setStep(3);
        state("info", "hourglass-split", "กำลังตรวจสอบสลิป ใช้เวลาไม่นาน");
      }
    } catch (e) { /* ลองใหม่รอบถัดไป */ }
  }
  function startPolling() { lock(true); btn.innerHTML = spinner + "กำลังตรวจสอบ"; poll(); timer = setInterval(poll, 3000); }

  btn.addEventListener("click", async () => {
    if (!file) return;
    lock(true);
    btn.innerHTML = spinner + "กำลังอัปโหลด";
    const fd = new FormData();
    fd.append("image", file);
    const res = await LMH.post(box.dataset.uploadUrl, fd, true);
    if (!res.ok) { lock(false); btn.innerHTML = btnHtml; state("bad", "x-circle-fill", res.data.error || "อัปโหลดไม่สำเร็จ"); return; }
    setStep(2);
    startPolling();
  });

  // เปิดหน้ากลับมาตอนออเดอร์กำลังตรวจอยู่
  if (box.dataset.initialStatus === "reviewing") { setStep(3); startPolling(); }
})();
