// คุกกี้: จำตัวเลือกของผู้ใช้ใน cookie `lmh_consent` (all | necessary) 180 วัน
// ตอนนี้เว็บไม่มีคุกกี้วิเคราะห์/โฆษณา ตัวเลือกนี้ใช้คุมสคริปต์เสริมที่อาจเพิ่มภายหลัง: ให้เช็ก LMH.consent.allows("analytics") ก่อนโหลดเสมอ
(function () {
  const NAME = "lmh_consent", DAYS = 180;
  const read = () => {
    const m = document.cookie.match(new RegExp("(?:^|; )" + NAME + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : null;
  };
  const write = (v) => {
    document.cookie = `${NAME}=${v}; max-age=${DAYS * 86400}; path=/; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
  };
  const el = document.getElementById("cookieBanner");
  const show = () => { if (!el) return; el.hidden = false; requestAnimationFrame(() => el.classList.add("is-in")); };
  const hide = () => { if (!el) return; el.classList.remove("is-in"); setTimeout(() => { el.hidden = true; }, 250); };

  window.LMH = window.LMH || {};
  LMH.consent = {
    get: read,
    allows: (category) => category === "necessary" || read() === "all",
  };

  if (!el) return;
  if (!read()) setTimeout(show, 700);

  document.addEventListener("click", (e) => {
    const choice = e.target.closest("[data-consent]");
    if (choice) {
      write(choice.dataset.consent);
      hide();
      document.dispatchEvent(new CustomEvent("lmh:consent", { detail: choice.dataset.consent }));
      return;
    }
    if (e.target.closest("[data-cookie-settings]")) { e.preventDefault(); show(); }
  });
})();
