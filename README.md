# 🎙️ ClassCaption

**Real-time lecture translation over your classroom Wi-Fi — fully offline.**

You lecture in English. Your Mac transcribes you in real time, translates each
sentence into **Chinese** and **Vietnamese** with a local LLM, and streams
captions to your students' phones over the local network. Each student picks their
language and **reads *and* hears** the lecture through their headphones. No audio
ever leaves the room — no cloud, no accounts, no internet required.

Built for teachers with international students who find a fast English lecture hard
to follow.

```
Your Mac (the engine)                              Student phones (headphones)
┌───────────────────────────────────────┐   Wi-Fi   ┌────────────────────────┐
│ mic → whisper.cpp   (English text)     │  (LAN)    │ open http://<mac>:5005 │
│     → Ollama LLM    → 中文 / Tiếng Việt │ ───────▶ │  /student              │
│     → broadcast to everyone (SSE)      │  captions │ read caption + hear it │
└───────────────────────────────────────┘           └────────────────────────┘
```

Typical delay from speaking to a student hearing it: **~2–4 seconds** (transcription
+ translation; the network itself is milliseconds).

---

## Requirements

- **macOS on Apple Silicon** (uses whisper.cpp's Metal backend).
- **[Homebrew](https://brew.sh)** — for `whisper-cpp`, `ffmpeg`, `sdl2`.
- **Python 3.10+**.
- **[Ollama](https://ollama.com)** with a translation model (default: `gemma4`).

## Setup (once)

```bash
./install.sh            # system deps + Python venv + speech model (~465 MB)
ollama pull gemma4      # the translation model (if you don't have it)
```

## Run a class

```bash
./run.sh
```

1. The **Teacher Console** opens (`http://<your-mac-ip>:5005/live`) with a big QR code.
2. **Students** join the same Wi-Fi, scan the QR (or type the address), pick **中文**
   or **Tiếng Việt**, tap **Start**, and put on headphones.
3. Click **▶ Start lecture** and talk. Watch the live feed confirm it's working.
4. Click **■ Stop lecture** when done.

Students each control their own audio on/off, text size, speed, and can toggle
"keep up with live" vs. "play everything."

---

## ⚠️ The Wi-Fi gotcha (read before your first class)

Many campus networks enable **client isolation** (AP isolation), which blocks
devices on the same Wi-Fi from reaching each other. If students **can't open the
link**, that's almost certainly why. **Test it before class.** Workarounds:

1. **Phone hotspot** — connect your Mac *and* the students to your phone's hotspot.
   Traffic stays local; no mobile data is used.
2. **A cheap travel/pocket router** — everyone joins its Wi-Fi. Best for a recurring class.
3. **Ask campus IT** to allow device-to-device traffic on a specific SSID.

Find your Mac's address anytime: `ipconfig getifaddr en0`.

---

## Getting the best quality

- **Use a headset, lapel, or USB mic**, not the built-in laptop mic. A close mic
  transcribes far more accurately and stops Whisper from inventing text during pauses.
  Set it in **System Settings → Sound → Input**.
- Speak in complete sentences with natural pauses — captions finalize at each pause.
- If you see spurious lines during silence, raise the detection threshold:
  `VAD_THOLD=0.80 ./run.sh` (default 0.70).
- For more accuracy on technical vocabulary, use a bigger model:
  ```bash
  curl -L -o models/ggml-medium.en.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.en.bin
  STREAM_MODEL="$(pwd)/models/ggml-medium.en.bin" ./run.sh
  ```

## Configuration (environment variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `5005` | Web server port |
| `VAD_THOLD` | `0.70` | Voice-activity threshold; higher = ignore quieter sound |
| `VAD_LENGTH_MS` | `8000` | Max length of one caption chunk (ms) |
| `STREAM_MODEL` | `models/ggml-small.en.bin` | Whisper model for live English |
| `OLLAMA_MODEL` | `gemma4` | Local LLM used for translation |
| `CAPTURE_DEVICE` | `-1` | Mic device index (`-1` = system default) |

## Add another language

Edit `LANGUAGES` in `live.py` — one entry flows through the translator, the student
language picker, and the on-device speech automatically:

```python
"ko": {"label": "한국어", "english": "Korean", "bcp47": "ko-KR", "say_voice": "Yuna"},
```

Check `say -v '?'` for an installed macOS voice for the server-side fallback.

---

## How it works

- **Speech-to-text:** `whisper-stream` (whisper.cpp) in VAD mode emits one clean
  block per spoken sentence; `live.py` parses it, trims overlap, and filters
  non-speech artifacts.
- **Translation:** one warm Ollama call per sentence returns both languages (~1 s),
  with thinking disabled for speed/consistency.
- **Delivery:** Server-Sent Events (`/stream`) — one-directional, auto-reconnecting,
  perfect for receive-only student devices. Tiny text packets, not audio.
- **Speech on the phone:** each browser speaks the caption with its built-in voice
  (Web Speech API); phones lacking a Chinese/Vietnamese voice fall back to audio
  rendered by your Mac's `say` voices, served from `/say`.

## Limitations

- Best for **clear English** delivered into a decent mic; accuracy drops on noisy
  far-field audio.
- Whisper can occasionally invent text during long silences (a close mic + `VAD_THOLD`
  handle it in practice).
- Machine translation is a strong comprehension aid, not a certified interpretation.

## License

MIT
