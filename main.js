/**
 * GestureSys v3.0 — Frontend Controller
 * ─────────────────────────────────────────────────────────
 * 15-gesture recognition · ASL alpha · Virtual AI Mouse
 *
 * Keyboard shortcuts
 *   Space / Enter  → toggle camera
 *   W              → Word mode
 *   A              → Alpha mode
 *   M              → Mouse mode
 *   C              → Clear history
 *   S              → Speak current gesture
 */
"use strict";

// ── All gesture metadata (word / alpha / mouse) ───────────────────
const GESTURES_META = {
  word: {
    thumbs_up:  { label: "THUMBS UP",  emoji: "👍" },
    peace:      { label: "PEACE",      emoji: "✌️" },
    open_palm:  { label: "OPEN PALM",  emoji: "🖐️" },
    fist:       { label: "POWER",      emoji: "✊" },
    pointing:   { label: "POINTING",   emoji: "👉" },
    rock:       { label: "ROCK ON",    emoji: "🤘" },
    ok:         { label: "OKAY",       emoji: "👌" },
    pinch:      { label: "PINCH",      emoji: "🤏" },
    three:      { label: "THREE",      emoji: "3️⃣" },
    four:       { label: "FOUR",       emoji: "4️⃣" },
    shaka:      { label: "HANG LOOSE", emoji: "🤙" },
    love_ily:   { label: "I LOVE YOU", emoji: "🤟" },
    finger_gun: { label: "FINGER GUN", emoji: "👆" },
    pinky_up:   { label: "PINKY UP",   emoji: "🙏" },
    vulcan:     { label: "LIVE LONG",  emoji: "🖖" },
  },
  alpha: {
    thumbs_up:  { label: "A",   emoji: "A"  },
    peace:      { label: "V",   emoji: "V"  },
    open_palm:  { label: "B",   emoji: "B"  },
    fist:       { label: "S",   emoji: "S"  },
    pointing:   { label: "D",   emoji: "D"  },
    rock:       { label: "N",   emoji: "N"  },
    ok:         { label: "F",   emoji: "F"  },
    pinch:      { label: "C",   emoji: "C"  },
    three:      { label: "W",   emoji: "W"  },
    four:       { label: "4",   emoji: "4"  },
    shaka:      { label: "Y",   emoji: "Y"  },
    love_ily:   { label: "ILY", emoji: "🤟" },
    finger_gun: { label: "L",   emoji: "L"  },
    pinky_up:   { label: "I",   emoji: "I"  },
    vulcan:     { label: "🖖",  emoji: "🖖" },
  },
  mouse: {
    mouse_move:         { label: "MOVE",         emoji: "☝️" },
    mouse_left_click:   { label: "LEFT CLICK",   emoji: "👆" },
    mouse_right_click:  { label: "RIGHT CLICK",  emoji: "🤙" },
    mouse_scroll_up:    { label: "SCROLL UP",    emoji: "🖐️" },
    mouse_scroll_down:  { label: "SCROLL DOWN",  emoji: "✊" },
    mouse_drag:         { label: "DRAG",         emoji: "🤏" },
    mouse_double_click: { label: "DOUBLE CLICK", emoji: "✌️" },
  },
};

// ── DOM refs ──────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const EL = {
  toggleBtn:    $("toggle-btn"),
  btnIcon:      $("btn-icon"),
  btnLabel:     $("btn-label"),
  videoFeed:    $("video-feed"),
  camOverlay:   $("cam-overlay"),
  rec:          $("rec"),
  statusPill:   $("status-pill"),
  statusText:   $("status-text"),
  fpsVal:       $("fps-val"),
  handsVal:     $("hands-val"),
  modeBadge:    $("mode-badge"),
  gEmoji:       $("g-emoji"),
  gLabel:       $("g-label"),
  confChip:     $("conf-chip"),
  confBar:      $("conf-bar"),
  confGlow:     $("conf-glow"),
  confPct:      $("conf-pct"),
  legendGrid:   $("legend-grid"),
  legendCount:  $("legend-count"),
  modeWord:     $("mode-word"),
  modeAlpha:    $("mode-alpha"),
  modeMouse:    $("mode-mouse"),
  mouseRefPanel:$("mouse-ref-panel"),
  mouseLiveLabel:$("mouse-live-label"),
  histList:     $("history-list"),
  histCount:    $("hist-count"),
  toast:        $("toast"),
  bgCanvas:     $("bg-canvas"),
};

// ── App state ─────────────────────────────────────────────────────
const ST = {
  running:     false,
  mode:        "word",
  lastGesture: null,
  lastHistLen: -1,
  pollTimer:   null,
  histTimer:   null,
};

// ── Toast helper ──────────────────────────────────────────────────
let _toastT = null;
function toast(msg, cls = "") {
  EL.toast.textContent = msg;
  EL.toast.className   = "toast show" + (cls ? " " + cls : "");
  clearTimeout(_toastT);
  _toastT = setTimeout(() => EL.toast.classList.remove("show"), 2500);
}

// ── Camera toggle ──────────────────────────────────────────────────
async function toggleCamera() {
  ST.running ? await stopCamera() : await startCamera();
}

async function startCamera() {
  try {
    const d = await postJSON("/api/start");
    if (d.status === "started" || d.status === "already_running") {
      ST.running = true;
      applyRunningUI(true);
      startPolling();
      toast("▶ DETECTION ACTIVE");
    }
  } catch { toast("⚠ CONNECTION ERROR", "o"); }
}

async function stopCamera() {
  try { await postJSON("/api/stop"); } catch {}
  ST.running = false;
  applyRunningUI(false);
  stopPolling();
  resetGesture();
  toast("■ DETECTION STOPPED");
}

function applyRunningUI(on) {
  EL.toggleBtn.classList.toggle("active", on);
  EL.btnIcon.textContent  = on ? "■" : "▶";
  EL.btnLabel.textContent = on ? "STOP DETECTION" : "START DETECTION";
  EL.camOverlay.classList.toggle("hidden", on);
  EL.videoFeed.src = on ? "/video_feed" : "";
  EL.statusPill.classList.toggle("online", on);
  EL.statusText.textContent = on ? "ONLINE" : "OFFLINE";
  EL.rec.classList.toggle("active", on);
  document.querySelectorAll(".corner").forEach(c => c.classList.toggle("glow", on));
}

// ── Polling ───────────────────────────────────────────────────────
function startPolling() {
  clearInterval(ST.pollTimer);
  clearInterval(ST.histTimer);
  ST.pollTimer = setInterval(pollStatus,  140);
  ST.histTimer = setInterval(pollHistory, 700);
}
function stopPolling() {
  clearInterval(ST.pollTimer);
  clearInterval(ST.histTimer);
  ST.pollTimer = ST.histTimer = null;
  EL.fpsVal.textContent   = "--";
  EL.handsVal.textContent = "0";
}

async function pollStatus() {
  try {
    const d = await fetchJSON("/api/status");
    EL.fpsVal.textContent   = d.fps   ?? "--";
    EL.handsVal.textContent = d.hands ?? "0";

    if (!d.running && ST.running) {
      ST.running = false;
      applyRunningUI(false);
      stopPolling();
      resetGesture();
      toast("⚠ CAMERA DISCONNECTED", "o");
      return;
    }

    updateGestureDisplay(d);

    // Sync mode if server changed it
    if (d.mode && d.mode !== ST.mode) {
      _applyModeUI(d.mode);
    }
  } catch {}
}

async function pollHistory() {
  try {
    const d = await fetchJSON("/api/history");
    renderHistory(d.history || []);
  } catch {}
}

// ── Gesture display ───────────────────────────────────────────────
function updateGestureDisplay(d) {
  const g    = d.gesture;
  const conf = d.confidence || 0;

  if (g !== ST.lastGesture) {
    ST.lastGesture = g;
    EL.gEmoji.textContent = d.emoji || "✋";
    EL.gEmoji.classList.remove("g-pop");
    void EL.gEmoji.offsetWidth;
    EL.gEmoji.classList.add("g-pop");

    if (g) {
      EL.gLabel.textContent = d.label || g.toUpperCase();
      EL.gLabel.classList.remove("idle");
    } else {
      resetGesture();
    }
    updateLegendActive(g);
    if (ST.mode === "mouse") updateMouseRefActive(g);
  }

  const pct = Math.round(conf * 100);
  EL.confChip.textContent    = g ? `${pct}%` : "—";
  EL.confBar.style.width     = `${pct}%`;
  EL.confGlow.style.width    = `${pct}%`;
  EL.confPct.textContent     = `${pct}%`;
}

function resetGesture() {
  EL.gEmoji.textContent = "✋";
  EL.gLabel.textContent = "WAITING…";
  EL.gLabel.classList.add("idle");
  EL.confChip.textContent = "—";
  EL.confBar.style.width = EL.confGlow.style.width = "0%";
  EL.confPct.textContent = "0%";
  ST.lastGesture = null;
  updateLegendActive(null);
  updateMouseRefActive(null);
}

// ── Legend ────────────────────────────────────────────────────────
function buildLegend(mode) {
  const meta  = GESTURES_META[mode] || GESTURES_META.word;
  const count = Object.keys(meta).length;
  EL.legendCount.textContent = `${count} SIGNS`;
  EL.legendGrid.innerHTML    = "";

  Object.entries(meta).forEach(([key, info]) => {
    const el       = document.createElement("div");
    el.className   = "legend-item";
    el.dataset.key = key;
    el.innerHTML   = `<span class="l-emoji">${info.emoji}</span><span class="l-label">${info.label}</span>`;
    EL.legendGrid.appendChild(el);
  });
}

function updateLegendActive(key) {
  const isMouse = ST.mode === "mouse";
  document.querySelectorAll(".legend-item").forEach(el => {
    const match = el.dataset.key === key;
    el.classList.toggle("act",       match && !isMouse);
    el.classList.toggle("act-mouse", match && isMouse);
  });
}

// ── Mouse reference panel ─────────────────────────────────────────
function updateMouseRefActive(gestureKey) {
  document.querySelectorAll(".mref-row").forEach(r =>
    r.classList.remove("active-action"));
  if (!gestureKey) {
    EL.mouseLiveLabel.textContent = "IDLE";
    return;
  }
  const row = document.querySelector(`.mref-row[data-action="${gestureKey}"]`);
  if (row) {
    row.classList.add("active-action");
    const actEl = row.querySelector(".mref-act");
    EL.mouseLiveLabel.textContent = actEl ? actEl.textContent : gestureKey.replace("mouse_","").toUpperCase();
  }
}

// ── Mode switching ────────────────────────────────────────────────
async function setMode(mode) {
  if (mode === ST.mode) return;
  try {
    const d = await postJSON("/api/mode", { mode });
    if (d.status === "ok") {
      _applyModeUI(mode);
      toast(`MODE → ${mode.toUpperCase()}`, mode === "mouse" ? "m" : "");
    }
  } catch { toast("⚠ MODE SWITCH FAILED", "o"); }
}

function _applyModeUI(mode) {
  ST.mode = mode;
  EL.modeWord.classList.toggle("active",  mode === "word");
  EL.modeAlpha.classList.toggle("active", mode === "alpha");
  EL.modeMouse.classList.toggle("active", mode === "mouse");
  EL.modeBadge.textContent = mode.toUpperCase();
  EL.mouseRefPanel.style.display = (mode === "mouse") ? "block" : "none";
  buildLegend(mode);
  resetGesture();
}

// ── History ───────────────────────────────────────────────────────
function renderHistory(history) {
  if (history.length === ST.lastHistLen) return;
  ST.lastHistLen = history.length;
  EL.histCount.textContent = `${history.length} entr${history.length === 1 ? "y" : "ies"}`;
  EL.histList.innerHTML = "";

  if (!history.length) {
    EL.histList.innerHTML = `<span class="hist-empty">No gestures detected yet</span>`;
    return;
  }
  history.forEach(e => {
    const el = document.createElement("div");
    el.className = "h-entry";
    el.title     = `Click to speak: ${e.label}`;
    el.innerHTML = `
      <span class="he-emoji">${e.emoji || "✋"}</span>
      <span class="he-label">${e.label}</span>
      <span class="he-conf">${Math.round(e.confidence * 100)}%</span>
      <span class="he-time">${e.time}</span>`;
    el.onclick = () => speakText(e.label);
    EL.histList.appendChild(el);
  });
}

async function clearHistory() {
  try {
    await postJSON("/api/clear_history");
    ST.lastHistLen = -1;
    EL.histList.innerHTML = `<span class="hist-empty">No gestures detected yet</span>`;
    EL.histCount.textContent = "0 entries";
    toast("HISTORY CLEARED");
  } catch { toast("⚠ CLEAR FAILED", "o"); }
}

// ── TTS ───────────────────────────────────────────────────────────
async function speakCurrent() {
  const lbl = EL.gLabel.textContent;
  if (!lbl || lbl === "WAITING…") { toast("NO GESTURE TO SPEAK"); return; }
  speakText(lbl);
}
async function speakText(text) {
  try {
    const d = await postJSON("/api/tts", { text });
    if (d.status === "speaking") toast(`🔊 ${d.text}`);
  } catch { toast("⚠ TTS FAILED", "o"); }
}

// ── Fetch helpers ─────────────────────────────────────────────────
async function fetchJSON(url) {
  const r = await fetch(url);
  return r.json();
}
async function postJSON(url, body = {}) {
  const r = await fetch(url, {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify(body),
  });
  return r.json();
}

// ── Animated background canvas ────────────────────────────────────
(function initBG() {
  const cv  = EL.bgCanvas;
  const ctx = cv.getContext("2d");
  let W, H, particles = [];

  const CHARS = "アイウエオカキクケコ0123456789ABCDEF";
  const mkP = () => ({
    x:     Math.random() * W,
    y:     Math.random() * H - H,
    size:  Math.random() * 1.5 + 0.5,
    speed: Math.random() * 0.45 + 0.08,
    alpha: Math.random() * 0.3 + 0.04,
    drift: (Math.random() - 0.5) * 0.3,
    char:  CHARS[Math.floor(Math.random() * CHARS.length)],
  });

  function resize() {
    W = cv.width  = window.innerWidth;
    H = cv.height = window.innerHeight;
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = "rgba(0,255,157,.02)";
    ctx.lineWidth   = 1;
    for (let x = 0; x < W; x += 60) {
      ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke();
    }
    for (let y = 0; y < H; y += 60) {
      ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke();
    }

    // Particles
    ctx.font = "11px 'Share Tech Mono', monospace";
    const col = ST.mode === "mouse" ? "#b060ff" : "#00ff9d";
    particles.forEach(p => {
      ctx.globalAlpha = p.alpha;
      ctx.fillStyle   = col;
      ctx.fillText(p.char, p.x, p.y);
      p.y     += p.speed;
      p.x     += p.drift;
      p.alpha -= 0.0005;
      if (p.y > H + 12 || p.alpha <= 0) Object.assign(p, mkP(), { y: -10 });
    });
    ctx.globalAlpha = 1;
    requestAnimationFrame(draw);
  }

  window.addEventListener("resize", () => {
    resize();
    particles = Array.from({ length: 90 }, mkP);
  });
  resize();
  particles = Array.from({ length: 90 }, mkP);
  draw();
})();

// ── Keyboard shortcuts ────────────────────────────────────────────
document.addEventListener("keydown", e => {
  if (document.activeElement.tagName === "INPUT") return;
  switch (e.key) {
    case " ": case "Enter": toggleCamera(); break;
    case "w": case "W":    setMode("word");  break;
    case "a": case "A":    setMode("alpha"); break;
    case "m": case "M":    setMode("mouse"); break;
    case "c": case "C":    clearHistory();   break;
    case "s": case "S":    speakCurrent();   break;
  }
});

// ── Init ──────────────────────────────────────────────────────────
(function init() {
  buildLegend("word");
  resetGesture();
  _applyModeUI("word");
  console.log(
    "%c GestureSys v3.0 ",
    "background:#00ff9d;color:#040c10;font-weight:bold;padding:4px 10px;border-radius:4px;",
    "\n 15 gestures | SPACE=camera | W=word | A=alpha | M=mouse | C=clear | S=speak"
  );
})();
