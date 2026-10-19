"""
GestureSys v3.0 — Hand Gesture Recognition + Virtual AI Mouse
==============================================================
Three operating modes:
  word   — Human-readable gesture labels (15 signs)
  alpha  — ASL-inspired letter / symbol mapping (15 signs)
  mouse  — Full OS virtual mouse control

Run:    python app.py
Open:   http://localhost:5000

─────────────────────────────────────────────────────────────
15 Detectable Gestures (word / alpha modes)
─────────────────────────────────────────────────────────────
 #  Internal Key   Word Label      Alpha
 1  thumbs_up      THUMBS UP       A
 2  peace          PEACE           V
 3  open_palm      OPEN PALM       B
 4  fist           POWER           S
 5  pointing       POINTING        D
 6  rock           ROCK ON         N
 7  ok             OKAY            F
 8  pinch          PINCH           C   ← NEW
 9  three          THREE           W   ← NEW
10  four           FOUR            4   ← NEW
11  shaka          HANG LOOSE      Y   ← NEW
12  love_ily       I LOVE YOU      ILY ← NEW
13  finger_gun     FINGER GUN      L   ← NEW
14  pinky_up       PINKY UP        I   ← NEW
15  vulcan         LIVE LONG       🖖  ← NEW

─────────────────────────────────────────────────────────────
Mouse Mode Gesture Map
─────────────────────────────────────────────────────────────
  ☝  Index only         → MOVE
  ✌  Index+Middle close  → LEFT CLICK
  ✌  Index+Middle wide   → DOUBLE CLICK
  🤏 Thumb+Index pinch   → DRAG
  🤙 Pinky only          → RIGHT CLICK
  🖐  Open palm          → SCROLL UP
  ✊  Fist               → SCROLL DOWN
"""

import os, ssl, math, time, threading, urllib.request
from datetime import datetime
from collections import deque

import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import pyttsx3
from flask import Flask, render_template, Response, jsonify, request

from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_utils

# ── pyautogui safety ───────────────────────────────────────────────────
pyautogui.FAILSAFE = False   # set True if you want corner-abort
pyautogui.PAUSE    = 0       # remove built-in delay

# ── Configuration ──────────────────────────────────────────────────────
MODEL_URL  = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
              "hand_landmarker/float16/1/hand_landmarker.task")
MODEL_PATH      = os.path.join(os.path.dirname(__file__), "model", "hand_landmarker.task")
MAX_HISTORY     = 60
TTS_COOLDOWN    = 2.0
GESTURE_HOLD    = 7       # frames gesture must be stable (non-mouse modes)
STREAM_FPS      = 24

# Virtual-mouse tuning
CAM_W, CAM_H    = 640, 480
MOUSE_SMOOTH    = 5       # EMA divisor — higher = smoother, more lag
MOUSE_MARGIN    = 55      # px dead-zone at frame edges
CLICK_D         = 0.045   # normalised index–middle distance → click
CLICK_CD        = 0.38    # seconds between click events
DRAG_D          = 0.042   # thumb–index normalised distance → drag
SCROLL_CD       = 0.12    # seconds between scroll ticks
SCROLL_AMT      = 4       # lines per tick
DBL_CLICK_D     = 0.065   # wider index–middle spread → double-click

# ── Landmark indices ───────────────────────────────────────────────────
WRIST                          = 0
THUMB_TIP, THUMB_IP, THUMB_MCP = 4, 3, 2
INDEX_TIP, INDEX_PIP, INDEX_MCP= 8, 6, 5
MIDDLE_TIP, MIDDLE_PIP         = 12, 10
RING_TIP,   RING_PIP           = 16, 14
PINKY_TIP,  PINKY_PIP          = 20, 18
MIDDLE_MCP, RING_MCP, PINKY_MCP= 9, 13, 17

# ── Word-mode gesture dictionary (15 gestures) ────────────────────────
WORD_GESTURES = {
    "thumbs_up":  {"label": "THUMBS UP",  "emoji": "👍", "color": (0,200,255),  "tint": (0,60,100)},
    "peace":      {"label": "PEACE",      "emoji": "✌️", "color": (180,60,255), "tint": (55,0,90)},
    "open_palm":  {"label": "OPEN PALM",  "emoji": "🖐️", "color": (0,255,180),  "tint": (0,100,60)},
    "fist":       {"label": "POWER",      "emoji": "✊", "color": (50,80,255),  "tint": (15,25,100)},
    "pointing":   {"label": "POINTING",   "emoji": "👉", "color": (0,220,255),  "tint": (0,75,85)},
    "rock":       {"label": "ROCK ON",    "emoji": "🤘", "color": (255,30,180), "tint": (90,0,70)},
    "ok":         {"label": "OKAY",       "emoji": "👌", "color": (30,255,180), "tint": (0,95,70)},
    # ── New gestures ──────────────────────────────────────────────────
    "pinch":      {"label": "PINCH",      "emoji": "🤏", "color": (255,200,0),  "tint": (80,60,0)},
    "three":      {"label": "THREE",      "emoji": "3️⃣", "color": (0,180,255),  "tint": (0,60,80)},
    "four":       {"label": "FOUR",       "emoji": "4️⃣", "color": (160,0,255),  "tint": (50,0,80)},
    "shaka":      {"label": "HANG LOOSE", "emoji": "🤙", "color": (255,130,0),  "tint": (85,45,0)},
    "love_ily":   {"label": "I LOVE YOU", "emoji": "🤟", "color": (255,50,140), "tint": (80,0,45)},
    "finger_gun": {"label": "FINGER GUN", "emoji": "👆", "color": (0,255,220),  "tint": (0,90,75)},
    "pinky_up":   {"label": "PINKY UP",   "emoji": "🙏", "color": (130,0,255),  "tint": (40,0,80)},
    "vulcan":     {"label": "LIVE LONG",  "emoji": "🖖", "color": (0,180,255),  "tint": (0,55,85)},
}

# ── Alpha-mode gesture dictionary (ASL-inspired) ─────────────────────
ALPHA_GESTURES = {
    "thumbs_up":  {"label": "A",   "emoji": "A",  "color": (0,200,255),  "tint": (0,60,100)},
    "peace":      {"label": "V",   "emoji": "V",  "color": (180,60,255), "tint": (55,0,90)},
    "open_palm":  {"label": "B",   "emoji": "B",  "color": (0,255,180),  "tint": (0,100,60)},
    "fist":       {"label": "S",   "emoji": "S",  "color": (50,80,255),  "tint": (15,25,100)},
    "pointing":   {"label": "D",   "emoji": "D",  "color": (0,220,255),  "tint": (0,75,85)},
    "rock":       {"label": "N",   "emoji": "N",  "color": (255,30,180), "tint": (90,0,70)},
    "ok":         {"label": "F",   "emoji": "F",  "color": (30,255,180), "tint": (0,95,70)},
    "pinch":      {"label": "C",   "emoji": "C",  "color": (255,200,0),  "tint": (80,60,0)},
    "three":      {"label": "W",   "emoji": "W",  "color": (0,180,255),  "tint": (0,60,80)},
    "four":       {"label": "4",   "emoji": "4",  "color": (160,0,255),  "tint": (50,0,80)},
    "shaka":      {"label": "Y",   "emoji": "Y",  "color": (255,130,0),  "tint": (85,45,0)},
    "love_ily":   {"label": "ILY", "emoji": "🤟", "color": (255,50,140), "tint": (80,0,45)},
    "finger_gun": {"label": "L",   "emoji": "L",  "color": (0,255,220),  "tint": (0,90,75)},
    "pinky_up":   {"label": "I",   "emoji": "I",  "color": (130,0,255),  "tint": (40,0,80)},
    "vulcan":     {"label": "🖖",  "emoji": "🖖", "color": (0,180,255),  "tint": (0,55,85)},
}

# ── Mouse-mode gesture dictionary ─────────────────────────────────────
MOUSE_GESTURES = {
    "mouse_move":         {"label": "MOVE",         "emoji": "☝️",  "color": (0,230,255),  "tint": (0,80,80)},
    "mouse_left_click":   {"label": "LEFT CLICK",   "emoji": "👆",  "color": (0,255,100),  "tint": (0,100,30)},
    "mouse_right_click":  {"label": "RIGHT CLICK",  "emoji": "🤙",  "color": (255,150,0),  "tint": (80,40,0)},
    "mouse_scroll_up":    {"label": "SCROLL UP",    "emoji": "🖐️",  "color": (255,255,0),  "tint": (80,80,0)},
    "mouse_scroll_down":  {"label": "SCROLL DOWN",  "emoji": "✊",  "color": (0,80,255),   "tint": (0,20,120)},
    "mouse_drag":         {"label": "DRAG",         "emoji": "🤏",  "color": (255,60,180), "tint": (80,0,60)},
    "mouse_double_click": {"label": "DOUBLE CLICK", "emoji": "✌️",  "color": (100,255,80), "tint": (20,80,10)},
}

# ── Shared application state ───────────────────────────────────────────
app_state = {
    "running":                  False,
    "frame":                    None,
    "gesture":                  None,
    "confidence":               0.0,
    "history":                  deque(maxlen=MAX_HISTORY),
    "mode":                     "word",   # "word" | "alpha" | "mouse"
    "last_tts_time":            0.0,
    "last_registered_gesture":  None,
    "gesture_hold_count":       0,
    "frame_count":              0,
    "fps":                      0.0,
    "hands_detected":           0,
}
state_lock    = threading.Lock()
camera_thread = None

# ── Model downloader ───────────────────────────────────────────────────
def ensure_model():
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    if os.path.exists(MODEL_PATH):
        return True
    print("[INFO] Downloading hand_landmarker.task (first run)…")
    for verify in (True, False):
        try:
            ctx = (ssl.create_default_context() if verify
                   else ssl._create_unverified_context())
            with urllib.request.urlopen(MODEL_URL, context=ctx) as r:
                with open(MODEL_PATH, "wb") as f:
                    f.write(r.read())
            print("[INFO] Model ready.")
            return True
        except Exception as exc:
            if verify:
                continue
            print(f"[ERROR] Model download failed: {exc}")
            return False

# ── Geometry helpers ───────────────────────────────────────────────────
def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)

def _finger_extended(tip, pip, mcp=None, thresh=0.07):
    return tip.y < pip.y - thresh

def _finger_curled(tip, pip, thresh=0.04):
    return tip.y > pip.y + thresh


# ══════════════════════════════════════════════════════════════════════
#  GESTURE CLASSIFIER  (15 gestures, most-specific first)
# ══════════════════════════════════════════════════════════════════════
def detect_gesture(lm):
    """
    Rule-based geometric classifier.
    Returns (gesture_key, confidence_float).

    Gesture ordering ensures no false positives between similar signs.
    """
    t_tip = lm[THUMB_TIP];  t_ip = lm[THUMB_IP];   t_mcp = lm[THUMB_MCP]
    i_tip = lm[INDEX_TIP];  i_pip = lm[INDEX_PIP];  i_mcp = lm[INDEX_MCP]
    m_tip = lm[MIDDLE_TIP]; m_pip = lm[MIDDLE_PIP]
    r_tip = lm[RING_TIP];   r_pip = lm[RING_PIP]
    p_tip = lm[PINKY_TIP];  p_pip = lm[PINKY_PIP]

    # ── Extension state for each finger ───────────────────────────────
    i_ext = _finger_extended(i_tip, i_pip)
    m_ext = _finger_extended(m_tip, m_pip)
    r_ext = _finger_extended(r_tip, r_pip)
    p_ext = _finger_extended(p_tip, p_pip)

    # Thumb: two separate checks
    thumb_up   = t_tip.y < t_ip.y - 0.025        # tip clearly above IP joint
    thumb_side = abs(t_tip.x - t_mcp.x) > 0.10   # thumb spread sideways
    thumb_ext  = thumb_up or thumb_side

    # Key distances
    pinch_d  = _dist(t_tip, i_tip)    # thumb ↔ index
    im_d     = _dist(i_tip, m_tip)    # index ↔ middle
    mr_d     = _dist(m_tip, r_tip)    # middle ↔ ring
    rp_d     = _dist(r_tip, p_tip)    # ring ↔ pinky

    # Curl state (used to tighten checks)
    i_curl = _finger_curled(i_tip, i_pip)
    m_curl = _finger_curled(m_tip, m_pip)
    r_curl = _finger_curled(r_tip, r_pip)
    p_curl = _finger_curled(p_tip, p_pip)

    ext_n = sum([i_ext, m_ext, r_ext, p_ext])

    # ── 1. PINCH ─────────────────────────────────────────────────────
    # Thumb + index very close; middle/ring/pinky curled
    if pinch_d < 0.055 and i_curl and m_curl and r_curl:
        conf = round(min(1.0, 1.0 - pinch_d * 13), 2)
        return "pinch", conf

    # ── 2. OK ─────────────────────────────────────────────────────────
    # Thumb–index circle; middle/ring/pinky all extended
    if pinch_d < 0.08 and m_ext and r_ext and p_ext:
        conf = round(min(1.0, 1.0 - pinch_d * 6), 2)
        return "ok", conf

    # ── 3. THUMBS UP ──────────────────────────────────────────────────
    # Thumb strictly up; all 4 fingers curled
    if thumb_up and i_curl and m_curl and r_curl and p_curl:
        conf = round(min(1.0, 0.80 + _dist(t_tip, i_pip) * 1.5), 2)
        return "thumbs_up", conf

    # ── 4. SHAKA / HANG LOOSE ─────────────────────────────────────────
    # Thumb + pinky extended; index + middle + ring all curled
    if thumb_ext and p_ext and i_curl and m_curl and r_curl:
        conf = round(min(1.0, 0.82 + abs(t_tip.x - p_tip.x) * 0.4), 2)
        return "shaka", conf

    # ── 5. I LOVE YOU (ILY) ───────────────────────────────────────────
    # Thumb + index + pinky; middle + ring curled
    if thumb_ext and i_ext and p_ext and m_curl and r_curl:
        conf = round(min(1.0, 0.80), 2)
        return "love_ily", conf

    # ── 6. FINGER GUN (L-shape) ───────────────────────────────────────
    # Index up + thumb spreading sideways; middle/ring/pinky curled
    if i_ext and thumb_side and m_curl and r_curl and not p_ext:
        conf = round(min(1.0, 0.78 + abs(t_tip.x - i_tip.x) * 0.5), 2)
        return "finger_gun", conf

    # ── 7. POINTING ───────────────────────────────────────────────────
    # Only index extended; others curled
    if i_ext and m_curl and r_curl and not p_ext:
        conf = round(min(1.0, 0.80), 2)
        return "pointing", conf

    # ── 8. ROCK ON (Devil Horns) ──────────────────────────────────────
    # Index + pinky up; middle + ring curled; thumb NOT up
    if i_ext and p_ext and m_curl and r_curl and not thumb_ext:
        conf = round(min(1.0, 0.78 + abs(i_tip.x - p_tip.x) * 0.5), 2)
        return "rock", conf

    # ── 9. PINKY UP ───────────────────────────────────────────────────
    # Only pinky extended; all others curled; thumb NOT up/side
    if p_ext and i_curl and m_curl and r_curl and not thumb_ext:
        conf = round(min(1.0, 0.76), 2)
        return "pinky_up", conf

    # ── 10. PEACE / VICTORY ───────────────────────────────────────────
    # Index + middle extended; ring + pinky down
    if i_ext and m_ext and not r_ext and not p_ext:
        conf = round(min(1.0, 0.82 + abs(i_tip.y - m_tip.y) * 0.3), 2)
        return "peace", conf

    # ── 11. THREE ─────────────────────────────────────────────────────
    # Index + middle + ring extended; pinky down
    if i_ext and m_ext and r_ext and not p_ext:
        conf = round(min(1.0, 0.78), 2)
        return "three", conf

    # ── 12. VULCAN SALUTE (🖖) ────────────────────────────────────────
    # All 4 fingers up; notable gap between middle and ring
    if i_ext and m_ext and r_ext and p_ext:
        if mr_d > max(im_d, rp_d) * 1.6:
            conf = round(min(1.0, 0.74 + (mr_d - max(im_d, rp_d)) * 3), 2)
            return "vulcan", conf
        # ── 13. FOUR (all 4, thumb tucked) ───────────────────────────
        if not thumb_ext:
            return "four", round(min(1.0, 0.76), 2)
        # ── 14. OPEN PALM (all 4 + thumb spread) ─────────────────────
        return "open_palm", round(min(1.0, 0.70 + ext_n * 0.06), 2)

    # ── 15. FIST ──────────────────────────────────────────────────────
    # All 4 curled; thumb NOT pointing up
    if i_curl and m_curl and r_curl and p_curl and not thumb_up:
        conf = round(min(1.0, 0.82 + _dist(i_tip, i_mcp) * 0.4), 2)
        return "fist", conf

    return None, 0.0


# ══════════════════════════════════════════════════════════════════════
#  VIRTUAL MOUSE CONTROLLER
# ══════════════════════════════════════════════════════════════════════
class VirtualMouse:
    """
    Translates raw MediaPipe hand landmarks into OS mouse events.

    Gesture → Action:
      ☝  Index only            → Move cursor (index tip = cursor)
      ✌  Index+Mid close       → Left click
      ✌  Index+Mid wide spread → Double click
      🤏 Thumb+Index pinch      → Drag
      🤙 Pinky only             → Right click
      🖐  Open palm (4 fingers) → Scroll up
      ✊  Fist                  → Scroll down
    """

    def __init__(self):
        self.sw, self.sh        = pyautogui.size()
        self.prev_x = self.prev_y = 0.0
        self.last_click_t       = 0.0
        self.last_scroll_t      = 0.0
        self.last_dbl_t         = 0.0
        self.dragging           = False

    # ── Map normalised coords → screen pixels with margin ─────────────
    def _map(self, nx, ny):
        sx = float(np.interp(nx * CAM_W,
                             [MOUSE_MARGIN, CAM_W - MOUSE_MARGIN],
                             [0, self.sw]))
        sy = float(np.interp(ny * CAM_H,
                             [MOUSE_MARGIN, CAM_H - MOUSE_MARGIN],
                             [0, self.sh]))
        return np.clip(sx, 0, self.sw - 1), np.clip(sy, 0, self.sh - 1)

    # ── Exponential moving average smoothing ──────────────────────────
    def _smooth(self, tx, ty):
        cx = self.prev_x + (tx - self.prev_x) / MOUSE_SMOOTH
        cy = self.prev_y + (ty - self.prev_y) / MOUSE_SMOOTH
        self.prev_x, self.prev_y = cx, cy
        return cx, cy

    def process(self, lm):
        """Evaluate landmarks, fire mouse events. Returns (action_key, conf)."""
        t_tip = lm[THUMB_TIP];  t_ip = lm[THUMB_IP]
        i_tip = lm[INDEX_TIP];  i_pip = lm[INDEX_PIP]; i_mcp = lm[INDEX_MCP]
        m_tip = lm[MIDDLE_TIP]; m_pip = lm[MIDDLE_PIP]
        r_tip = lm[RING_TIP];   r_pip = lm[RING_PIP]
        p_tip = lm[PINKY_TIP];  p_pip = lm[PINKY_PIP]

        i_ext = _finger_extended(i_tip, i_pip)
        m_ext = _finger_extended(m_tip, m_pip)
        r_ext = _finger_extended(r_tip, r_pip)
        p_ext = _finger_extended(p_tip, p_pip)
        i_curl = _finger_curled(i_tip, i_pip)
        m_curl = _finger_curled(m_tip, m_pip)

        pinch_d = _dist(t_tip, i_tip)
        im_d    = _dist(i_tip, m_tip)

        now     = time.time()
        action  = None
        conf    = 0.0

        tx, ty = self._map(i_tip.x, i_tip.y)
        cx, cy = self._smooth(tx, ty)

        # ── DRAG: tight thumb–index pinch, no other fingers ───────────
        if pinch_d < DRAG_D and not m_ext and not r_ext and not p_ext:
            if not self.dragging:
                pyautogui.mouseDown(cx, cy, button="left")
                self.dragging = True
            else:
                pyautogui.moveTo(cx, cy)
            action = "mouse_drag"
            conf   = round(min(1.0, 1.0 - pinch_d * 18), 2)

        # ── LEFT CLICK: index+middle up, tips close ───────────────────
        elif i_ext and m_ext and im_d < CLICK_D and not r_ext and not p_ext:
            self._release_drag()
            if now - self.last_click_t > CLICK_CD:
                pyautogui.click(cx, cy)
                self.last_click_t = now
            action = "mouse_left_click"
            conf   = round(min(1.0, 1.0 - im_d * 15), 2)

        # ── DOUBLE CLICK: index+middle, wider spread ──────────────────
        elif i_ext and m_ext and CLICK_D <= im_d < DBL_CLICK_D and not r_ext and not p_ext:
            self._release_drag()
            if now - self.last_dbl_t > CLICK_CD * 2.5:
                pyautogui.doubleClick(cx, cy)
                self.last_dbl_t = now
            action = "mouse_double_click"
            conf   = 0.82

        # ── RIGHT CLICK: only pinky up ────────────────────────────────
        elif p_ext and not i_ext and not m_ext and not r_ext:
            self._release_drag()
            if now - self.last_click_t > CLICK_CD:
                pyautogui.rightClick(cx, cy)
                self.last_click_t = now
            action = "mouse_right_click"
            conf   = 0.86

        # ── SCROLL UP: open palm (4 fingers) ─────────────────────────
        elif i_ext and m_ext and r_ext and p_ext:
            self._release_drag()
            if now - self.last_scroll_t > SCROLL_CD:
                pyautogui.scroll(SCROLL_AMT)
                self.last_scroll_t = now
            action = "mouse_scroll_up"
            conf   = 0.88

        # ── SCROLL DOWN: fist ─────────────────────────────────────────
        elif i_curl and m_curl and not r_ext and not p_ext:
            self._release_drag()
            if now - self.last_scroll_t > SCROLL_CD:
                pyautogui.scroll(-SCROLL_AMT)
                self.last_scroll_t = now
            action = "mouse_scroll_down"
            conf   = 0.88

        # ── MOVE: only index up ───────────────────────────────────────
        elif i_ext and not m_ext and not r_ext and not p_ext:
            self._release_drag()
            pyautogui.moveTo(cx, cy)
            action = "mouse_move"
            conf   = 0.90

        # ── No gesture → release drag if held ────────────────────────
        else:
            self._release_drag()

        return action, conf

    def _release_drag(self):
        if self.dragging:
            try:
                pyautogui.mouseUp(button="left")
            except Exception:
                pass
            self.dragging = False

    def release(self):
        self._release_drag()


# Module-level mouse instance (reset each camera start)
_virtual_mouse = VirtualMouse()


# ── Frame annotation ───────────────────────────────────────────────────
def annotate_frame(img, result, mode, frame_count):
    """Draw skeleton + gesture labels. For mouse mode, drive VirtualMouse."""
    h, w = img.shape[:2]
    g_map    = (WORD_GESTURES  if mode == "word"  else
                ALPHA_GESTURES if mode == "alpha" else
                MOUSE_GESTURES)
    detected   = None
    confidence = 0.0

    for hand_lm, handedness in zip(result.hand_landmarks, result.handedness):

        if mode == "mouse":
            gesture_key, conf = _virtual_mouse.process(hand_lm)
        else:
            gesture_key, conf = detect_gesture(hand_lm)

        info  = g_map.get(gesture_key, {}) if gesture_key else {}
        color = info.get("color", (0,255,180))
        tint  = info.get("tint",  (0,50,50))

        # Subtle colour tint
        ov = img.copy()
        cv2.rectangle(ov, (0,0), (w,h), tint, -1)
        cv2.addWeighted(ov, 0.11, img, 0.89, 0, img)

        # Skeleton
        lmk_spec  = drawing_utils.DrawingSpec(color=color, thickness=3, circle_radius=5)
        conn_spec = drawing_utils.DrawingSpec(color=color, thickness=2)
        try:
            drawing_utils.draw_landmarks(
                img, hand_lm,
                vision.HandLandmarksConnections.HAND_CONNECTIONS,
                lmk_spec, conn_spec)
        except Exception:
            pass

        # Gesture label above hand
        if gesture_key:
            xs = [int(lm.x*w) for lm in hand_lm]
            ys = [int(lm.y*h) for lm in hand_lm]
            cx = sum(xs)//len(xs)
            cy = max(0, min(ys) - 60)
            label = info.get("label", gesture_key.upper())
            cv2.putText(img, label, (cx-3, cy+3), cv2.FONT_HERSHEY_DUPLEX, 1.0, (0,0,0), 4)
            cv2.putText(img, label, (cx,   cy),   cv2.FONT_HERSHEY_DUPLEX, 1.0, color,   2)
            detected, confidence = gesture_key, conf

        # Handedness badge
        bx = int(hand_lm[0].x*w)
        by = min(h-10, int(hand_lm[0].y*h)+25)
        cv2.putText(img, handedness[0].category_name, (bx-20,by),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150,220,255), 2)

        # Mouse cursor crosshair on index tip
        if mode == "mouse":
            ix = int(hand_lm[INDEX_TIP].x * w)
            iy = int(hand_lm[INDEX_TIP].y * h)
            cv2.circle(img, (ix,iy), 12, color, 2)
            cv2.line(img, (ix-18,iy),(ix+18,iy), color, 2)
            cv2.line(img, (ix,iy-18),(ix,iy+18), color, 2)

    return img, detected, confidence


# ── HUD overlay ───────────────────────────────────────────────────────
def _draw_hud(frame, mode):
    h, w = frame.shape[:2]
    gc   = (0, 255, 157)
    sz   = 22

    # Corner brackets
    for (x,y),(dx,dy) in [((10,10),(1,1)),((w-10,10),(-1,1)),
                           ((10,h-10),(1,-1)),((w-10,h-10),(-1,-1))]:
        cv2.line(frame,(x,y),(x+dx*sz,y),gc,2)
        cv2.line(frame,(x,y),(x,y+dy*sz),gc,2)

    # Mode badge (bottom-right)
    labels = {"word":"WORD MODE","alpha":"ALPHA MODE","mouse":"MOUSE MODE 🖱"}
    txt = labels.get(mode, mode.upper())
    (tw,th),_ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
    bx, by = w-tw-18, h-12
    cv2.rectangle(frame,(bx-6,by-th-4),(bx+tw+4,by+4),(0,20,14),-1)
    cv2.rectangle(frame,(bx-6,by-th-4),(bx+tw+4,by+4),gc,1)
    cv2.putText(frame,txt,(bx,by),cv2.FONT_HERSHEY_SIMPLEX,0.48,gc,1)

    # Mouse cheat-sheet (top-left)
    if mode == "mouse":
        tips = [
            "INDEX ONLY   → MOVE",
            "IDX+MID NEAR → L-CLICK",
            "IDX+MID WIDE → DBL-CLICK",
            "THUMB PINCH  → DRAG",
            "PINKY ONLY   → R-CLICK",
            "OPEN PALM    → SCROLL UP",
            "FIST         → SCROLL DN",
        ]
        for i, tip in enumerate(tips):
            cv2.putText(frame, tip, (12, 26+i*19),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0,220,140), 1)


# ── TTS ───────────────────────────────────────────────────────────────
def speak_async(text):
    def _inner():
        try:
            e = pyttsx3.init()
            e.setProperty("rate",   165)
            e.setProperty("volume", 0.9)
            e.say(text); e.runAndWait(); e.stop()
        except Exception as ex:
            print(f"[TTS] {ex}")
    threading.Thread(target=_inner, daemon=True).start()


# ── Camera / Detection thread ─────────────────────────────────────────
def camera_worker():
    global app_state, _virtual_mouse

    use_model = ensure_model()
    detector  = None

    if use_model:
        try:
            opts = vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
                num_hands=2,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                running_mode=vision.RunningMode.VIDEO,
            )
            detector = vision.HandLandmarker.create_from_options(opts)
        except Exception as e:
            print(f"[ERROR] MediaPipe: {e}")
            use_model = False

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open camera.")
        with state_lock:
            app_state["running"] = False
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
    cap.set(cv2.CAP_PROP_FPS,          STREAM_FPS)

    _virtual_mouse = VirtualMouse()   # fresh instance

    fps_timer = time.time()
    fps_cnt = frame_cnt = hold_cnt = 0
    last_gst = None
    print("[INFO] Camera started.")

    try:
        while True:
            with state_lock:
                if not app_state["running"]:
                    break
                mode = app_state["mode"]

            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)
            frame_cnt += 1
            fps_cnt   += 1
            det_gst    = None
            conf       = 0.0

            if use_model and detector:
                try:
                    rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    ts_ms  = int(cap.get(cv2.CAP_PROP_POS_MSEC)) or frame_cnt * 33
                    result = detector.detect_for_video(mp_img, ts_ms)
                    n      = len(result.hand_landmarks)
                    if n > 0:
                        frame, det_gst, conf = annotate_frame(frame, result, mode, frame_cnt)
                    with state_lock:
                        app_state["hands_detected"] = n
                except Exception as e:
                    print(f"[WARN] {e}")

            _draw_hud(frame, mode)

            # Stability filter (skip for mouse — needs immediate response)
            if mode == "mouse":
                stable = det_gst
            else:
                if det_gst == last_gst and det_gst:
                    hold_cnt += 1
                else:
                    hold_cnt = 0
                    last_gst = det_gst
                stable = det_gst if hold_cnt >= GESTURE_HOLD else None

            with state_lock:
                app_state["gesture"]     = stable or det_gst
                app_state["confidence"]  = conf
                app_state["frame_count"] = frame_cnt

                if (stable
                        and stable != app_state["last_registered_gesture"]
                        and (mode == "mouse" or hold_cnt == GESTURE_HOLD)):
                    g_map = (WORD_GESTURES  if mode == "word"  else
                             ALPHA_GESTURES if mode == "alpha" else
                             MOUSE_GESTURES)
                    info  = g_map.get(stable, {})
                    app_state["history"].appendleft({
                        "gesture":    stable,
                        "label":      info.get("label", stable),
                        "emoji":      info.get("emoji", ""),
                        "confidence": conf,
                        "time":       datetime.now().strftime("%H:%M:%S"),
                        "mode":       mode,
                    })
                    app_state["last_registered_gesture"] = stable
                    now = time.time()
                    if (mode != "mouse"
                            and now - app_state["last_tts_time"] > TTS_COOLDOWN):
                        app_state["last_tts_time"] = now
                        speak_async(info.get("label", stable))

                ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ok2:
                    app_state["frame"] = buf.tobytes()

            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                with state_lock:
                    app_state["fps"] = round(fps_cnt / elapsed, 1)
                fps_cnt   = 0
                fps_timer = time.time()

            time.sleep(1 / STREAM_FPS)

    finally:
        _virtual_mouse.release()
        cap.release()
        if detector:
            detector.close()
        print("[INFO] Camera stopped.")


# ── Placeholder frame ─────────────────────────────────────────────────
_PLACEHOLDER = None

def _make_placeholder():
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    for x in range(0,640,40): cv2.line(img,(x,0),(x,480),(0,30,20),1)
    for y in range(0,480,40): cv2.line(img,(0,y),(640,y),(0,30,20),1)
    for txt,y_,sc in [("CAMERA OFFLINE",240,1.0),("PRESS START TO BEGIN",272,0.5)]:
        (tw,_),_ = cv2.getTextSize(txt,cv2.FONT_HERSHEY_DUPLEX,sc,2)
        cv2.putText(img,txt,((640-tw)//2,y_),cv2.FONT_HERSHEY_DUPLEX,sc,(0,80,50),2)
    _,buf = cv2.imencode(".jpg",img,[cv2.IMWRITE_JPEG_QUALITY,78])
    return buf.tobytes()


# ══════════════════════════════════════════════════════════════════════
#  FLASK APPLICATION
# ══════════════════════════════════════════════════════════════════════
app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        _PLACEHOLDER = _make_placeholder()

    def generate():
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while True:
            with state_lock:
                running = app_state["running"]
                fb      = app_state.get("frame")
            yield boundary + (fb if running and fb else _PLACEHOLDER) + b"\r\n"
            time.sleep(1 / STREAM_FPS)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/start", methods=["POST"])
def start_camera():
    global camera_thread
    with state_lock:
        if app_state["running"]:
            return jsonify({"status": "already_running"})
        app_state.update({"running": True, "gesture": None,
                          "confidence": 0.0, "hands_detected": 0})
    camera_thread = threading.Thread(target=camera_worker, daemon=True)
    camera_thread.start()
    return jsonify({"status": "started"})


@app.route("/api/stop", methods=["POST"])
def stop_camera():
    _virtual_mouse.release()
    with state_lock:
        app_state.update({"running": False, "gesture": None,
                          "confidence": 0.0, "frame": None, "hands_detected": 0})
    return jsonify({"status": "stopped"})


@app.route("/api/status")
def get_status():
    with state_lock:
        mode  = app_state["mode"]
        g_key = app_state["gesture"]
        g_map = (WORD_GESTURES  if mode == "word"  else
                 ALPHA_GESTURES if mode == "alpha" else
                 MOUSE_GESTURES)
        info  = g_map.get(g_key, {}) if g_key else {}
        return jsonify({
            "running":    app_state["running"],
            "gesture":    g_key,
            "label":      info.get("label", ""),
            "emoji":      info.get("emoji", ""),
            "confidence": app_state["confidence"],
            "mode":       mode,
            "fps":        app_state["fps"],
            "hands":      app_state["hands_detected"],
        })


@app.route("/api/history")
def get_history():
    with state_lock:
        return jsonify({"history": list(app_state["history"])})


@app.route("/api/clear_history", methods=["POST"])
def clear_history():
    with state_lock:
        app_state["history"].clear()
        app_state["last_registered_gesture"] = None
    return jsonify({"status": "cleared"})


@app.route("/api/mode", methods=["POST"])
def set_mode():
    data = request.get_json(silent=True) or {}
    m    = data.get("mode", "word")
    if m not in ("word", "alpha", "mouse"):
        return jsonify({"error": "Invalid mode — use 'word', 'alpha', or 'mouse'"}), 400
    if m != "mouse":
        _virtual_mouse.release()
    with state_lock:
        app_state.update({"mode": m, "last_registered_gesture": None,
                          "gesture": None, "confidence": 0.0})
    return jsonify({"status": "ok", "mode": m})


@app.route("/api/tts", methods=["POST"])
def trigger_tts():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if text:
        speak_async(text)
        return jsonify({"status": "speaking", "text": text})
    return jsonify({"error": "No text provided"}), 400


@app.route("/api/gestures")
def get_gestures():
    with state_lock:
        mode = app_state["mode"]
    g_map = (WORD_GESTURES  if mode == "word"  else
             ALPHA_GESTURES if mode == "alpha" else
             MOUSE_GESTURES)
    return jsonify({
        "mode": mode,
        "gestures": {k: {"label": v["label"], "emoji": v["emoji"]}
                     for k, v in g_map.items()},
    })


# ── Entry point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    w, h = pyautogui.size()
    print("=" * 62)
    print("  ✋  GESTURESYS v3.0  ·  15 Gestures + Virtual AI Mouse")
    print("=" * 62)
    print(f"  Screen: {w}×{h}  |  Open → http://localhost:5000")
    print("  Modes: WORD · ALPHA · MOUSE")
    print("  Press Ctrl+C to stop")
    print("=" * 62)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
