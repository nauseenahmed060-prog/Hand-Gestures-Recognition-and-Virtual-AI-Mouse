# ✋ GestureSys v3.0 — 15 Hand Signs + Virtual AI Mouse

Real-time hand gesture recognition with **15 distinct signs**, ASL letter mapping,
and full virtual mouse control — 100% local, no cloud.

---

## ⚡ Quick Start

```bash
pip install -r requirements.txt
python app.py
# → open http://localhost:5000
```

---

## ✋ 15 Detectable Gestures

| # | Key         | Word Label   | Alpha (ASL) | Description                         |
|---|-------------|--------------|-------------|-------------------------------------|
| 1 | thumbs_up   | THUMBS UP    | A           | Thumb up, 4 fingers curled          |
| 2 | peace       | PEACE        | V           | Index + middle up                   |
| 3 | open_palm   | OPEN PALM    | B           | All 4 fingers + thumb spread        |
| 4 | fist        | POWER        | S           | All fingers curled                  |
| 5 | pointing    | POINTING     | D           | Only index finger up                |
| 6 | rock        | ROCK ON      | N           | Index + pinky up, no thumb          |
| 7 | ok          | OKAY         | F           | Thumb-index circle, 3 fingers up    |
| 8 | pinch       | PINCH        | C           | Thumb+index close, others curled    |
| 9 | three       | THREE        | W           | Index+middle+ring up                |
|10 | four        | FOUR         | 4           | All 4 fingers, thumb tucked         |
|11 | shaka       | HANG LOOSE   | Y           | Thumb + pinky, others curled        |
|12 | love_ily    | I LOVE YOU   | ILY         | Thumb + index + pinky extended      |
|13 | finger_gun  | FINGER GUN   | L           | Index up + thumb sideways (L-shape) |
|14 | pinky_up    | PINKY UP     | I           | Only pinky extended                 |
|15 | vulcan      | LIVE LONG    | 🖖          | All 4 up, wide middle-ring gap      |

---

## 🖱️ Mouse Mode Gesture Map

| Gesture         | Action       |
|-----------------|--------------|
| ☝️ Index only    | Move cursor  |
| ✌️ Index+Mid near| Left click   |
| ✌️ Index+Mid wide| Double click |
| 🤏 Thumb pinch   | Drag         |
| 🤙 Pinky only    | Right click  |
| 🖐️ Open palm     | Scroll up    |
| ✊ Fist          | Scroll down  |

---

## ⌨️ Keyboard Shortcuts

| Key   | Action         |
|-------|----------------|
| Space | Toggle camera  |
| W     | Word mode      |
| A     | Alphabet mode  |
| M     | Mouse mode     |
| C     | Clear history  |
| S     | Speak gesture  |

---

## 🛠 Troubleshooting

| Problem             | Fix                                              |
|---------------------|--------------------------------------------------|
| pyautogui on Linux  | `sudo apt install python3-tk python3-dev scrot`  |
| TTS on Linux        | `sudo apt install espeak`                        |
| Wrong camera        | Change `cv2.VideoCapture(0)` to `(1)` in app.py |
| Gesture jitter      | Increase `GESTURE_HOLD` in app.py               |
| False pinch clicks  | Increase `CLICK_D` / `DRAG_D` in app.py         |
