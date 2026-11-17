// Player: ฝัง YouTube (Unlisted) ผ่าน IFrame API
// - เริ่มเล่นที่ตำแหน่งที่เรียนค้าง (server คำนวณถอย 10 วินาทีให้แล้ว → data-start)
// - รายงานตำแหน่ง + เวลาที่ดูจริงทุก 10 วินาทีขณะเล่น (Ajax) และตอน pause/จบ/ปิดหน้า
(function () {
  const root = document.getElementById("player-root");
  if (!root) return;
  const cfg = {
    videoId: root.dataset.videoId,
    lessonId: parseInt(root.dataset.lessonId, 10),
    start: parseInt(root.dataset.start, 10) || 0,
    track: root.dataset.track === "1",
    url: root.dataset.progressUrl,
    nextUrl: root.dataset.nextUrl,
  };
  let player = null;
  let playingSince = null; // เวลา (ms) ที่เริ่มนับรอบนี้ — นับเป็น wall-clock จึงไม่เพี้ยนเมื่อปรับความเร็ว/กรอวิดีโอ
  let pendingSeconds = 0;
  let timer = null;

  function flushTimer() {
    if (playingSince !== null) {
      const now = Date.now();
      pendingSeconds += (now - playingSince) / 1000;
      playingSince = now;
    }
  }

  function report(useKeepalive) {
    if (!cfg.track || !player || !player.getCurrentTime) return;
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

  function onStateChange(e) {
    const S = YT.PlayerState;
    if (e.data === S.PLAYING) {
      if (playingSince === null) playingSince = Date.now();
      if (!timer) timer = setInterval(() => report(false), 10000);
    } else {
      flushTimer();
      playingSince = null;
      if (timer) { clearInterval(timer); timer = null; }
      if (e.data === S.PAUSED || e.data === S.ENDED) report(false);
      if (e.data === S.ENDED && cfg.nextUrl) {
        LMH.toast("จบคลิปแล้ว กดคลิปถัดไปเพื่อเรียนต่อ", "ok");
        const next = document.getElementById("next-btn");
        if (next) { next.classList.remove("btn-dark"); next.classList.add("btn-primary"); }
      }
    }
  }

  window.onYouTubeIframeAPIReady = function () {
    player = new YT.Player("yt-player", {
      host: "https://www.youtube-nocookie.com", // ไม่ตั้งคุกกี้ของ YouTube จนกว่าจะกดเล่น
      videoId: cfg.videoId,
      playerVars: { rel: 0, modestbranding: 1, playsinline: 1, start: cfg.start, origin: location.origin },
      events: {
        onReady: function () {
          if (cfg.start > 0) {
            const m = Math.floor(cfg.start / 60), s = String(cfg.start % 60).padStart(2, "0");
            LMH.toast("เรียนต่อจากนาทีที่ " + m + ":" + s + " (ย้อนให้ 10 วินาที)", "info");
          }
        },
        onStateChange: onStateChange,
      },
    });
  };

  // แถบปุ่มใต้วิดีโอ: ย้อน/ข้าม 10 วินาที, ความเร็ว, จดโน้ต, เต็มจอ
  const $ = (id) => document.getElementById(id);
  const seekBy = (d) => { if (player && player.getCurrentTime) player.seekTo(Math.max(0, player.getCurrentTime() + d), true); };
  $("pl-back") && $("pl-back").addEventListener("click", () => seekBy(-10));
  $("pl-fwd") && $("pl-fwd").addEventListener("click", () => seekBy(10));
  $("pl-rate") && $("pl-rate").addEventListener("change", (e) => { if (player && player.setPlaybackRate) player.setPlaybackRate(parseFloat(e.target.value)); });
  $("pl-stamp") && $("pl-stamp").addEventListener("click", () => {
    const tab = document.querySelector('[data-bs-target="#tab-notes"]');
    if (tab) bootstrap.Tab.getOrCreateInstance(tab).show();
    const stamp = $("note-stamp");
    if (stamp) stamp.click();
  });
  $("pl-full") && $("pl-full").addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (root.requestFullscreen) root.requestFullscreen();
  });

  // ให้สมุดโน้ตเรียกใช้: อ่านเวลาปัจจุบัน / ข้ามไปยังเวลาที่ต้องการ
  window.LMHPlayer = {
    time: () => (player && player.getCurrentTime ? Math.floor(player.getCurrentTime()) : 0),
    seek: (sec) => { if (player && player.seekTo) { player.seekTo(sec, true); player.playVideo(); } },
  };

  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") report(true); });
  window.addEventListener("pagehide", () => report(true));

  const tag = document.createElement("script");
  tag.src = "https://www.youtube.com/iframe_api";
  document.head.appendChild(tag);
})();
