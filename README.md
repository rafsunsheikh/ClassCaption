<a id="readme-top"></a>

<!-- SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]
[![Offline][offline-shield]][offline-url]
[![Platform][platform-shield]][platform-url]

<!-- HEADER -->
<br />
<div align="center">
  <h1 align="center">🎙️ ClassCaption</h1>

  <p align="center">
    Real-time lecture translation over your classroom Wi-Fi — <strong>fully offline</strong>.
    <br />
    You speak English. Your students read <em>and</em> hear it in their own language, on their own phones.
    <br /><br />
    <a href="#getting-started"><strong>Get started »</strong></a>
    <br /><br />
    <a href="#usage">Usage</a>
    &middot;
    <a href="https://github.com/rafsunsheikh/classcaption/issues">Report Bug</a>
    &middot;
    <a href="https://github.com/rafsunsheikh/classcaption/issues">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#how-it-works">How It Works</a></li>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li><a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#the-wi-fi-gotcha">The Wi-Fi Gotcha</a></li>
    <li><a href="#getting-the-best-quality">Getting The Best Quality</a></li>
    <li><a href="#configuration">Configuration</a></li>
    <li><a href="#add-another-language">Add Another Language</a></li>
    <li><a href="#limitations">Limitations</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

You lecture in English. Your Mac transcribes you in real time, translates each
sentence into **Chinese** and **Vietnamese** with a local LLM, and streams
captions to your students' phones over the local network. Each student picks their
language and **reads *and* hears** the lecture through their headphones.

**No audio ever leaves the room** — no cloud, no accounts, no internet required.

Built for teachers with international students who find a fast English lecture hard
to follow.

Typical delay from speaking to a student hearing it: **~2–4 seconds**
(transcription + translation; the network itself is milliseconds).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### How It Works

```
Your Mac (the engine)                              Student phones (headphones)
┌───────────────────────────────────────┐   Wi-Fi   ┌────────────────────────┐
│ mic → whisper.cpp   (English text)     │  (LAN)    │ open http://<mac>:5005 │
│     → Ollama LLM    → 中文 / Tiếng Việt │ ───────▶ │  /student              │
│     → broadcast to everyone (SSE)      │  captions │ read caption + hear it │
└───────────────────────────────────────┘           └────────────────────────┘
```

- **Speech-to-text** — `whisper-stream` (whisper.cpp) in VAD mode emits one clean
  block per spoken sentence; `live.py` parses it, trims overlap, and filters
  non-speech artifacts.
- **Translation** — one warm Ollama call per sentence returns both languages
  (~1 s), with thinking disabled for speed and consistency.
- **Delivery** — Server-Sent Events (`/stream`): one-directional, auto-reconnecting,
  perfect for receive-only student devices. Tiny text packets, not audio.
- **Speech on the phone** — each browser speaks the caption with its built-in voice
  (Web Speech API); phones lacking a Chinese/Vietnamese voice fall back to audio
  rendered by your Mac's `say` voices, served from `/say`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

[![Python][python-shield]][python-url]
[![Flask][flask-shield]][flask-url]
[![whisper.cpp][whisper-shield]][whisper-url]
[![Ollama][ollama-shield]][ollama-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

Everything runs on a single Mac. Set it up once, then launch a class in one command.

### Prerequisites

- **macOS on Apple Silicon** (uses whisper.cpp's Metal backend).
- **[Homebrew](https://brew.sh)** — for `whisper-cpp`, `ffmpeg`, `sdl2`.
- **Python 3.10+**.
- **[Ollama](https://ollama.com)** with a translation model (default: `gemma4`).

### Installation

```bash
# 1. System deps + Python venv + speech model (~465 MB)
./install.sh

# 2. Pull the translation model (if you don't have it)
ollama pull gemma4
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE -->
## Usage

Start a class:

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- WI-FI GOTCHA -->
## The Wi-Fi Gotcha

> [!WARNING]
> **Read this before your first class.**

Many campus networks enable **client isolation** (AP isolation), which blocks
devices on the same Wi-Fi from reaching each other. If students **can't open the
link**, that's almost certainly why. **Test it before class.** Workarounds:

1. **Phone hotspot** — connect your Mac *and* the students to your phone's hotspot.
   Traffic stays local; no mobile data is used.
2. **A cheap travel/pocket router** — everyone joins its Wi-Fi. Best for a recurring class.
3. **Ask campus IT** to allow device-to-device traffic on a specific SSID.

Find your Mac's address anytime:

```bash
ipconfig getifaddr en0
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- QUALITY -->
## Getting The Best Quality

- **Use a headset, lapel, or USB mic**, not the built-in laptop mic. A close mic
  transcribes far more accurately and stops Whisper from inventing text during pauses.
  Set it in **System Settings → Sound → Input**.
- Speak in complete sentences with natural pauses — captions finalize at each pause.
- If you see spurious lines during silence, raise the detection threshold:
  ```bash
  VAD_THOLD=0.80 ./run.sh   # default 0.70
  ```
- For more accuracy on technical vocabulary, use a bigger model:
  ```bash
  curl -L -o models/ggml-medium.en.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.en.bin
  STREAM_MODEL="$(pwd)/models/ggml-medium.en.bin" ./run.sh
  ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONFIGURATION -->
## Configuration

All configuration is via environment variables passed to `./run.sh`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `5005` | Web server port |
| `VAD_THOLD` | `0.70` | Voice-activity threshold; higher = ignore quieter sound |
| `VAD_LENGTH_MS` | `8000` | Max length of one caption chunk (ms) |
| `STREAM_MODEL` | `models/ggml-small.en.bin` | Whisper model for live English |
| `OLLAMA_MODEL` | `gemma4` | Local LLM used for translation |
| `CAPTURE_DEVICE` | `-1` | Mic device index (`-1` = system default) |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ADD LANGUAGE -->
## Add Another Language

Edit `LANGUAGES` in `live.py` — one entry flows through the translator, the student
language picker, and the on-device speech automatically:

```python
"ko": {"label": "한국어", "english": "Korean", "bcp47": "ko-KR", "say_voice": "Yuna"},
```

Check `say -v '?'` for an installed macOS voice for the server-side fallback.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LIMITATIONS -->
## Limitations

- Best for **clear English** delivered into a decent mic; accuracy drops on noisy
  far-field audio.
- Whisper can occasionally invent text during long silences (a close mic + `VAD_THOLD`
  handle it in practice).
- Machine translation is a strong comprehension aid, not a certified interpretation.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->
## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->
## Contact

Rafsun Sheikh — [@rafsunsheikh](https://github.com/rafsunsheikh)

Project Link: [https://github.com/rafsunsheikh/classcaption](https://github.com/rafsunsheikh/classcaption)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) — on-device speech-to-text
- [Ollama](https://ollama.com) — local LLM runtime for translation
- [Flask](https://flask.palletsprojects.com) — web server and SSE delivery
- [segno](https://github.com/heuer/segno) — QR code generation
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template) — README structure

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/rafsunsheikh/classcaption.svg?style=for-the-badge
[contributors-url]: https://github.com/rafsunsheikh/classcaption/graphs/contributors
[stars-shield]: https://img.shields.io/github/stars/rafsunsheikh/classcaption.svg?style=for-the-badge
[stars-url]: https://github.com/rafsunsheikh/classcaption/stargazers
[issues-shield]: https://img.shields.io/github/issues/rafsunsheikh/classcaption.svg?style=for-the-badge
[issues-url]: https://github.com/rafsunsheikh/classcaption/issues
[license-shield]: https://img.shields.io/github/license/rafsunsheikh/classcaption.svg?style=for-the-badge
[license-url]: https://github.com/rafsunsheikh/classcaption/blob/main/LICENSE
[offline-shield]: https://img.shields.io/badge/100%25-offline-success?style=for-the-badge
[offline-url]: #about-the-project
[platform-shield]: https://img.shields.io/badge/macOS-Apple%20Silicon-black?style=for-the-badge&logo=apple
[platform-url]: #prerequisites
[python-shield]: https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white
[python-url]: https://www.python.org
[flask-shield]: https://img.shields.io/badge/Flask-3.0+-000000?style=for-the-badge&logo=flask&logoColor=white
[flask-url]: https://flask.palletsprojects.com
[whisper-shield]: https://img.shields.io/badge/whisper.cpp-Metal-FF6F00?style=for-the-badge
[whisper-url]: https://github.com/ggerganov/whisper.cpp
[ollama-shield]: https://img.shields.io/badge/Ollama-LLM-white?style=for-the-badge&logo=ollama&logoColor=black
[ollama-url]: https://ollama.com
