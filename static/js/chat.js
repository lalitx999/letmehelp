// แชทบอทลอย: เก็บบทสนทนาใน sessionStorage, ส่ง Ajax ไป /chat/, แสดงผลแบบปลอดภัย (ไม่ใช้ innerHTML กับข้อความจากเซิร์ฟเวอร์)
(function () {
  const root = document.getElementById("chat");
  if (!root) return;
  const fab = document.getElementById("chatFab");
  const panel = document.getElementById("chatPanel");
  const log = document.getElementById("chatLog");
  const form = document.getElementById("chatForm");
  const input = document.getElementById("chatInput");
  const sugg = document.getElementById("chatSuggest");
  const modeEl = document.getElementById("chatMode");
  const url = root.dataset.url;

  // โหมดติวเตอร์: อยู่ในหน้าเรียน (มี #player-root) จะส่ง lesson_id ให้เซิร์ฟเวอร์ตรวจสิทธิ์
  const player = document.getElementById("player-root");
  const lessonId = player ? player.dataset.lessonId : null;
  const lessonTitle = player && document.querySelector("h1") ? document.querySelector("h1").textContent.trim() : "";
  const KEY = "lmh-chat-v1:" + (lessonId || "public");
  const PUBLIC_SUGGEST = ["คอร์สมีอะไรบ้าง", "ราคาเท่าไหร่", "ชำระเงินยังไง", "ทดลองเรียนฟรีได้ไหม"];
  const TUTOR_SUGGEST = ["อธิบายหัวข้อนี้ให้เข้าใจง่าย", "ขอตัวอย่างประโยค", "สรุปเป็นข้อๆ"];
  modeEl.textContent = lessonId ? "( ติวเตอร์ประจำคลิป )" : "( ตอบคำถาม )";

  let history = [];
  try { history = JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch (e) { history = []; }
  let busy = false;

  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(history.slice(-30))); } catch (e) { /* ไม่เป็นไร */ } };

  // แปลง **ตัวหนา** และ [ข้อความ](/path-ภายในเว็บ) เป็น DOM โดยไม่ใช้ innerHTML
  function inline(parent, text) {
    const re = /\*\*([^*]+)\*\*|\[([^\]]+)\]\((\/[^)\s]*)\)/g;
    let last = 0, m;
    while ((m = re.exec(text))) {
      if (m.index > last) parent.appendChild(document.createTextNode(text.slice(last, m.index)));
      if (m[1]) { const b = document.createElement("strong"); b.textContent = m[1]; parent.appendChild(b); }
      else if (!m[3].startsWith("//")) { const a = document.createElement("a"); a.href = m[3]; a.textContent = m[2]; parent.appendChild(a); }
      else parent.appendChild(document.createTextNode(m[0]));
      last = re.lastIndex;
    }
    if (last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
  }

  function bubble(role, text) {
    const el = document.createElement("div");
    el.className = "msg " + (role === "user" ? "user" : "bot");
    inline(el, text);
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function chips(list) {
    sugg.replaceChildren();
    (list || []).slice(0, 4).forEach((t) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip-btn"; b.textContent = t;
      b.addEventListener("click", () => send(t));
      sugg.appendChild(b);
    });
  }

  function greet() {
    const t = lessonId
      ? "กำลังเรียน \"" + (lessonTitle || "คลิปนี้") + "\" อยู่ ถามเรื่องเนื้อหา ไวยากรณ์ หรือเทคนิคทำข้อสอบได้เลย"
      : "สวัสดี ถามเรื่องคอร์ส ราคา การชำระเงิน หรือวิธีเรียนได้เลย";
    bubble("bot", t);
    chips(lessonId ? TUTOR_SUGGEST : PUBLIC_SUGGEST);
  }

  function render() {
    log.replaceChildren();
    if (!history.length) { greet(); return; }
    history.forEach((m) => bubble(m.role, m.content));
    chips(lessonId ? TUTOR_SUGGEST : PUBLIC_SUGGEST);
  }

  function typing() {
    const el = document.createElement("div");
    el.className = "msg bot typing"; el.setAttribute("aria-label", "กำลังพิมพ์");
    el.innerHTML = "<i></i><i></i><i></i>";
    log.appendChild(el); log.scrollTop = log.scrollHeight;
    return el;
  }

  async function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    busy = true; input.value = ""; chips([]);
    history.push({ role: "user", content: text.slice(0, 800) }); save();
    bubble("user", text);
    const dots = typing();
    let reply = "ขออภัย เกิดข้อผิดพลาด ลองใหม่อีกครั้งนะ", next = [];
    try {
      const res = await LMH.post(url, { messages: history, lesson_id: lessonId });
      if (res.data && res.data.reply) { reply = res.data.reply; next = res.data.suggestions || []; }
    } catch (e) { /* ใช้ข้อความ error ด้านบน */ }
    dots.remove();
    history.push({ role: "assistant", content: reply }); save();
    bubble("bot", reply);
    chips(next.length ? next : (lessonId ? TUTOR_SUGGEST : []));
    busy = false; input.focus();
  }

  function open(v) {
    panel.hidden = !v;
    root.classList.toggle("is-open", v);
    fab.setAttribute("aria-expanded", String(v));
    if (v) { if (!log.childElementCount) render(); setTimeout(() => input.focus(), 50); log.scrollTop = log.scrollHeight; }
  }

  fab.addEventListener("click", () => open(panel.hidden));
  document.getElementById("chatClose").addEventListener("click", () => { open(false); fab.focus(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) open(false); });
  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
})();
