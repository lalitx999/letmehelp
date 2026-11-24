// Player: ฝัง YouTube (Unlisted) แบบป้องกันลิงก์ — แนวเดียวกับหน้าเรียนของ ryu
// - ซ่อนปุ่มของ YouTube (controls=0, ปิดคีย์ลัด/ปุ่มเต็มจอ/วิดีโอแนะนำ) ตัว iframe ไม่รับเมาส์ มีแผ่นใสทับ
//   นักเรียนจึงกดโลโก้/ชื่อคลิป/แชร์/คลิกขวา "คัดลอก URL" ของ YouTube ไม่ได้ ใช้แถบปุ่มของเราแทน
// - iPhone/iPad ไม่ยอมเริ่มเล่นจากปุ่มของเรา ครั้งแรกต้องแตะที่ตัววิดีโอ: เปิดเฉพาะกลางจอให้แตะทะลุ
//   (หัว/ท้ายวิดีโอที่มีชื่อคลิปและโลโก้ยังมีแผ่นกันอยู่) พอเล่นแล้วปิดกลับทันที
// - เริ่มเล่นที่ตำแหน่งที่เรียนค้าง (server คำนวณถอย 10 วินาทีให้แล้ว → data-start)
// - รายงานตำแหน่ง + เวลาที่ดูจริงทุก 10 วินาทีขณะเล่น (Ajax) และตอน pause/จบ/ปิดหน้า
// หมายเหตุ: กันนักเรียนทั่วไปได้ แต่ไม่ใช่การเข้ารหัส — คนที่เปิด DevTools เป็นยังหา video id ได้
(function () {
  const root = document.getElementById("player-root");
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const cfg = {
    videoId: root.dataset.videoId,
    lessonId: parseInt(root.dataset.lessonId, 10),
    start: parseInt(root.dataset.start, 10) || 0,
    track: root.dataset.track === "1",
    url: root.dataset.progressUrl,
    nextUrl: root.dataset.nextUrl,
  };
  const stage = $("pl-stage");
  const isIOS = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

  let player = null;
  let ready = false;
  let started = false; // เคยเล่นได้จริงแล้วหรือยัง (iOS ต้องแตะที่วิดีโอครั้งแรก)
  let startTimer = null;
  let dragging = false;
  let playingSince = null; // เวลา (ms) ที่เริ่มนับรอบนี้ — นับเป็น wall-clock จึงไม่เพี้ยนเมื่อปรับความเร็ว/กรอวิดีโอ
  let pendingSeconds = 0;
  let timer = null;

  const fmt = (t) => {
    t = Math.max(0, Math.floor(t || 0));
    const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = String(t % 60).padStart(2, "0");
    return h ? h + ":" + String(m).padStart(2, "0") + ":" + s : m + ":" + s;
  };
  const setIcon = (btn, name) => { const u = btn && btn.querySelector("use"); if (u) u.setAttribute("href", u.getAttribute("href").replace(/#.*$/, "#" + name)); };

  /* ---------- รายงานความคืบหน้า ---------- */
  function flushTimer() {
    if (playingSince !== null) {
      const now = Date.now();
      pendingSeconds += (now - playingSince) / 1000;
      playingSince = now;
    }
  }

  function report(useKeepalive) {
    if (!cfg.track || !ready) return;
    flushTimer();
    const delta = Math.round(pendingSeconds);
    pendingSeconds -= delta;
    const body = JSON.stringify({
      lesson_id: cfg.lessonId,
      position: Math.floor(player.getCurrentTime()),
      duration: Math.floor(player.getDuration() || 0),
      delta: delta,
    });
    fetch(cfg.url, {
      method: "POST",
      keepalive: !!useKeepalive,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": LMH.cookie("csrftoken") },
      body: body,
    }).catch(() => {});
  }

  /* ---------- สถานะบนจอ ---------- */
  function tapThrough(on) {
    root.classList.toggle("tap-through", on);
    $("pl-taphint").hidden = !on;
    $("pl-bigplay").hidden = on;
  }

  function showPlaying(playing) {
    setIcon($("pl-play"), playing ? "pause-fill" : "play-fill");
    $("pl-play").setAttribute("aria-label", playing ? "หยุด" : "เล่น");
    root.classList.toggle("is-playing", playing);
    if (!root.classList.contains("tap-through")) $("pl-bigplay").hidden = playing;
  }

  function onStateChange(e) {
    const S = YT.PlayerState;
    if (e.data === S.PLAYING || e.data === S.BUFFERING) clearTimeout(startTimer);
    if (e.data === S.PLAYING) {
      if (!started) { started = true; tapThrough(false); }
      $("pl-end").hidden = true;
      showPlaying(true);
      $("pl-range").max = Math.floor(player.getDuration() || 0);
      $("pl-dur").textContent = fmt(player.getDuration());
      if (playingSince === null) playingSince = Date.now();
      if (!timer) timer = setInterval(() => report(false), 10000);
    } else {
      if (e.data !== S.BUFFERING) showPlaying(false);
      flushTimer();
      playingSince = null;
      if (timer) { clearInterval(timer); timer = null; }
      if (e.data === S.PAUSED || e.data === S.ENDED) report(false);
      if (e.data === S.ENDED) {
        $("pl-end").hidden = false; // บังหน้าวิดีโอแนะนำของ YouTube ตอนจบ
        $("pl-bigplay").hidden = true;
        const next = $("next-btn");
        if (next) { next.classList.remove("btn-dark"); next.classList.add("btn-primary"); }
      }
    }
  }

  /* ---------- ปุ่มควบคุม ---------- */
  function play() {
    if (!ready) return;
    player.playVideo();
    if (!started) {
      // เบราว์เซอร์อาจไม่ยอมให้เริ่มจากปุ่มของเรา (เช่น Safari บางรุ่น) → ให้แตะที่ตัววิดีโอแทน
      clearTimeout(startTimer);
      startTimer = setTimeout(() => { if (!started) tapThrough(true); }, 1800);
    }
  }
  function togglePlay() {
    if (!ready) return;
    if (player.getPlayerState() === YT.PlayerState.PLAYING) player.pauseVideo();
    else play();
  }
  const seekTo = (t) => { if (!ready) return; player.seekTo(Math.max(0, t), true); $("pl-cur").textContent = fmt(t); };
  const seekBy = (d) => { if (ready) seekTo(player.getCurrentTime() + d); };

  function toggleMute() {
    if (!ready) return;
    const muted = player.isMuted();
    if (muted) player.unMute(); else player.mute();
    setIcon($("pl-mute"), muted ? "volume-up" : "volume-mute");
    $("pl-mute").setAttribute("aria-label", muted ? "ปิดเสียง" : "เปิดเสียง");
  }

  // เต็มจอทั้งวิดีโอ + แถบปุ่ม (iPhone ไม่มี fullscreen API ของ element → ขยายเต็มหน้าจอด้วย CSS แทน)
  const fsEl = () => document.fullscreenElement || document.webkitFullscreenElement;
  const canFs = !!(stage.requestFullscreen || stage.webkitRequestFullscreen) && !/iPhone|iPod/.test(navigator.userAgent);
  const isFull = () => !!fsEl() || stage.classList.contains("is-fake-full");
  function fakeFull(on) { stage.classList.toggle("is-fake-full", on); document.body.classList.toggle("pl-lock", on); syncFull(); }
  function syncFull() { setIcon($("pl-full"), isFull() ? "fullscreen-exit" : "fullscreen"); $("pl-full").setAttribute("aria-label", isFull() ? "ออกจากเต็มจอ" : "เต็มจอ"); }
  function toggleFull() {
    if (stage.classList.contains("is-fake-full")) return fakeFull(false);
    if (fsEl()) return (document.exitFullscreen || document.webkitExitFullscreen).call(document);
    if (canFs) {
      const req = stage.requestFullscreen || stage.webkitRequestFullscreen;
      Promise.resolve(req.call(stage)).then(() => { try { screen.orientation.lock("landscape").catch(() => {}); } catch (e) { /* ไม่รองรับ */ } }).catch(() => fakeFull(true));
    } else fakeFull(true);
  }
  document.addEventListener("fullscreenchange", syncFull);
  document.addEventListener("webkitfullscreenchange", syncFull);

  $("pl-shield").addEventListener("click", togglePlay);
  $("pl-shield").addEventListener("dblclick", toggleFull);
  $("pl-bigplay").addEventListener("click", play);
  $("pl-play").addEventListener("click", togglePlay);
  $("pl-back").addEventListener("click", () => seekBy(-10));
  $("pl-fwd").addEventListener("click", () => seekBy(10));
  $("pl-mute").addEventListener("click", toggleMute);
  $("pl-full").addEventListener("click", toggleFull);
  $("pl-rate").addEventListener("change", (e) => { if (ready) player.setPlaybackRate(parseFloat(e.target.value)); });
  $("pl-replay").addEventListener("click", () => { $("pl-end").hidden = true; seekTo(0); play(); });
  $("pl-stamp") && $("pl-stamp").addEventListener("click", () => {
    const tab = document.querySelector('[data-bs-target="#tab-notes"]');
    if (tab) bootstrap.Tab.getOrCreateInstance(tab).show();
    const stamp = $("note-stamp");
    if (stamp) stamp.click();
  });

  const range = $("pl-range");
  range.addEventListener("input", () => { dragging = true; $("pl-cur").textContent = fmt(range.value); });
  range.addEventListener("change", () => { dragging = false; seekTo(+range.value); });

  setInterval(() => {
    if (!ready || dragging) return;
    const t = player.getCurrentTime() || 0, d = player.getDuration() || 0;
    if (d && +range.max !== Math.floor(d)) { range.max = Math.floor(d); $("pl-dur").textContent = fmt(d); }
    range.value = Math.floor(t);
    range.style.setProperty("--p", d ? (t / d) * 100 + "%" : "0%");
    $("pl-cur").textContent = fmt(t);
  }, 500);

  // คีย์ลัดของเราเอง (ของ YouTube ถูกปิด) — ไม่ทำงานขณะพิมพ์ในช่องโน้ต
  const typing = (el) => el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && stage.classList.contains("is-fake-full")) return fakeFull(false);
    if (typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.toLowerCase();
    const act = { " ": togglePlay, k: togglePlay, arrowleft: () => seekBy(-10), j: () => seekBy(-10), arrowright: () => seekBy(10), l: () => seekBy(10), m: toggleMute, f: toggleFull }[k];
    if (act && (k !== " " || !e.target.closest("button, a"))) { e.preventDefault(); act(); }
  });

  /* ---------- ลายน้ำ: ย้ายตำแหน่งเป็นระยะ ---------- */
  const wm = $("pl-wm");
  if (wm) {
    const spots = [[8, 10], [62, 14], [30, 46], [10, 72], [58, 70], [36, 22]];
    let i = 0;
    const move = () => { const [x, y] = spots[i++ % spots.length]; wm.style.left = x + "%"; wm.style.top = y + "%"; };
    move();
    setInterval(move, 15000);
  }

  /* ---------- กันคลิกขวา/ลาก/เลือกข้อความ/คีย์ลัดบันทึก-ดูซอร์ส ทั้งหน้าเรียน (ยกเว้นช่องพิมพ์) ---------- */
  const guard = (e) => { if (!typing(e.target)) e.preventDefault(); };
  ["contextmenu", "dragstart", "selectstart", "copy", "cut"].forEach((ev) => document.addEventListener(ev, guard));
  document.addEventListener("keydown", (e) => {
    const k = e.key.toLowerCase(), mod = e.ctrlKey || e.metaKey;
    const blocked = e.key === "F12" || (mod && ["s", "u", "p"].includes(k)) || (mod && (e.shiftKey || e.altKey) && ["i", "j", "c"].includes(k));
    if (blocked) e.preventDefault();
  });

  /* ---------- สร้าง player ---------- */
  window.onYouTubeIframeAPIReady = function () {
    player = new YT.Player("yt-player", {
      host: "https://www.youtube-nocookie.com", // ไม่ตั้งคุกกี้ของ YouTube จนกว่าจะกดเล่น
      videoId: cfg.videoId,
      playerVars: {
        controls: 0, disablekb: 1, fs: 0, rel: 0, iv_load_policy: 3, modestbranding: 1, playsinline: 1,
        start: cfg.start, origin: location.origin,
      },
      events: {
        onReady: function () {
          ready = true;
          const d = player.getDuration() || 0;
          range.max = Math.floor(d);
          $("pl-dur").textContent = fmt(d);
          $("pl-cur").textContent = fmt(cfg.start);
          if (isIOS) tapThrough(true);
          if (cfg.start > 0) LMH.toast("เรียนต่อจากนาทีที่ " + fmt(cfg.start) + " (ย้อนให้ 10 วินาที)", "info");
        },
        onStateChange: onStateChange,
      },
    });
  };

  // ให้สมุดโน้ตเรียกใช้: อ่านเวลาปัจจุบัน / ข้ามไปยังเวลาที่ต้องการ
  window.LMHPlayer = {
    time: () => (ready ? Math.floor(player.getCurrentTime()) : 0),
    seek: (sec) => { if (ready) { seekTo(sec); play(); } },
  };

  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") report(true); });
  window.addEventListener("pagehide", () => report(true));

  const tag = document.createElement("script");
  tag.src = "https://www.youtube.com/iframe_api";
  document.head.appendChild(tag);
})();
