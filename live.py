"""Live lecture pipeline: mic -> English (whisper-stream) -> zh/vi (Ollama) -> broadcast.

Runs entirely on-device. A background thread drives ``whisper-stream`` in VAD mode,
parses each finalized English utterance, translates it to Simplified Chinese and
Vietnamese with a local Ollama model (kept warm), and fans the result out to every
connected student browser through a thread-safe broadcast hub (consumed via SSE).

Design notes
------------
* whisper-stream ``--step 0`` = VAD mode: it waits for a natural pause, then prints
  one clean block per utterance::

      ### Transcription N START | t0 = .. | t1 = ..
      [00:00:00.000 --> 00:00:07.600]   <the sentence>
      ### Transcription N END

  That gives us sentence-level boundaries -- far better for translation than a
  sliding window that re-emits overlapping fragments.
* Two events are published per utterance: an instant English-only event (so the
  caption appears immediately) and a follow-up with the translations filled in.
  The browser merges them by ``seq``.
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# --- Configuration -----------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"

WHISPER_STREAM_BIN = os.environ.get("WHISPER_STREAM_BIN", "whisper-stream")
STREAM_MODEL = Path(os.environ.get("STREAM_MODEL", MODELS_DIR / "ggml-small.en.bin"))

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4")

# VAD tuning (overridable via env). length = max utterance window in ms;
# vad_thold = how confident the detector must be that speech is present.
VAD_LENGTH_MS = os.environ.get("VAD_LENGTH_MS", "8000")
VAD_THOLD = os.environ.get("VAD_THOLD", "0.70")  # raise if noise causes false triggers
CAPTURE_DEVICE = os.environ.get("CAPTURE_DEVICE", "-1")  # -1 = system default mic

# Target languages. Add more here and they flow through automatically.
LANGUAGES = {
    "zh": {"label": "中文 (简体)", "english": "Simplified Chinese",
           "bcp47": "zh-CN", "say_voice": "Tingting"},
    "vi": {"label": "Tiếng Việt", "english": "Vietnamese",
           "bcp47": "vi-VN", "say_voice": "Linh"},
}

_SEGMENT_RE = re.compile(r"^\[[0-9:.]+ --> [0-9:.]+\]\s*(.*)$")

# A line that is *entirely* wrapped in (...) or [...] is a stage direction
# Whisper invents on non-speech ("(door opens)", "[music]") -- never real lecture.
_BRACKETED_RE = re.compile(r"^[\[(].*[\])]$")
_ALNUM_RE = re.compile(r"[A-Za-z0-9À-￿]")

# Phrases Whisper commonly hallucinates on silence/ambient noise (from its
# training data: YouTube outros, captions boilerplate). Matched case-insensitively.
_HALLUCINATIONS = {
    "thanks for watching", "thank you for watching", "please subscribe",
    "subscribe to my channel", "like and subscribe", "see you next time",
    "thanks for listening", "you", "bye", "bye.", "thank you.",
}


def is_speech(text: str) -> bool:
    """Filter out Whisper's non-speech artifacts so students never see garbage."""
    t = text.strip()
    if len(t) < 2 or not _ALNUM_RE.search(t):
        return False
    if _BRACKETED_RE.match(t):
        return False
    if t.lower().strip(" .!?") in _HALLUCINATIONS:
        return False
    return True


# --- Broadcast hub -----------------------------------------------------------

class Hub:
    """Fan-out of caption events to any number of SSE subscribers.

    Each subscriber gets its own bounded queue; a slow/stalled client drops
    events rather than blocking the producer. Recent history is replayed to
    late joiners so a student who connects mid-sentence still gets context.
    """

    def __init__(self, history_size: int = 40):
        self._subs: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self._history: list[dict] = []
        self._history_size = history_size

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=200)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subs.discard(q)

    def history(self) -> list[dict]:
        with self._lock:
            return list(self._history)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)

    def publish(self, event: dict) -> None:
        with self._lock:
            if event.get("final"):
                self._history.append(event)
                del self._history[:-self._history_size]
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass


# --- Translation (Ollama) ----------------------------------------------------

def _ollama_generate(prompt: str, timeout: float = 30.0) -> str:
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,               # gemma is a thinking model; skip hidden
                                      # reasoning tokens (3-7x faster, consistent)
        "keep_alive": "30m",          # keep the model resident between sentences
        "options": {"temperature": 0.2, "num_predict": 256},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data.get("response") or "").strip()


def _clean_line(text: str) -> str:
    """Strip stray quotes/labels a model sometimes wraps around a translation."""
    text = text.strip().strip('"').strip("“”").strip()
    return text


def translate_all(text: str) -> dict[str, str]:
    """Translate one English sentence into every target language.

    One combined call (two output lines) keeps latency low; if the strict format
    isn't honoured we fall back to per-language calls so a student is never left
    without their translation.
    """
    prompt = (
        "You are a real-time interpreter for a university lecture. "
        "Translate the English sentence into Simplified Chinese and Vietnamese. "
        "Keep it natural and faithful. Output EXACTLY two lines, nothing else, "
        "no pinyin, no notes, no quotes:\n"
        "ZH: <Simplified Chinese>\n"
        "VI: <Vietnamese>\n\n"
        f'English: "{text}"'
    )
    out = {"zh": "", "vi": ""}
    try:
        resp = _ollama_generate(prompt)
        for line in resp.splitlines():
            m = re.match(r"^\s*ZH\s*[:：]\s*(.*)$", line, re.IGNORECASE)
            if m:
                out["zh"] = _clean_line(m.group(1))
            m = re.match(r"^\s*VI\s*[:：]\s*(.*)$", line, re.IGNORECASE)
            if m:
                out["vi"] = _clean_line(m.group(1))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        pass

    # Per-language fallback for anything the combined pass missed.
    for code, meta in LANGUAGES.items():
        if not out.get(code):
            try:
                single = _ollama_generate(
                    f"Translate this English lecture sentence into "
                    f"{meta['english']}. Output ONLY the translation, no quotes, "
                    f"no notes:\n\n{text}")
                out[code] = _clean_line(single.splitlines()[0]) if single else ""
            except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                out[code] = ""
    return out


def warm_up() -> bool:
    """Preload the Ollama model so the first real sentence isn't slow. Best-effort."""
    try:
        _ollama_generate("Reply with OK.", timeout=60)
        return True
    except Exception:
        return False


# --- Live pipeline controller ------------------------------------------------

class LivePipeline:
    """Owns the whisper-stream subprocess and the translation worker."""

    def __init__(self, hub: Hub):
        self.hub = hub
        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._translator: threading.Thread | None = None
        self._utterances: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self.running = False
        self.error: str | None = None
        self._seq = 0
        self._last_words: list[str] = []   # for trimming overlap between utterances
        self.started_at: float | None = None
        self.last_utterance_at: float | None = None
        self.count = 0

    # -- lifecycle --
    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            if not STREAM_MODEL.exists():
                raise RuntimeError(f"Model not found: {STREAM_MODEL}")
            cmd = [
                WHISPER_STREAM_BIN, "-m", str(STREAM_MODEL), "-l", "en",
                "--step", "0", "--length", str(VAD_LENGTH_MS),
                "-vth", str(VAD_THOLD), "-c", str(CAPTURE_DEVICE), "-t", "4",
            ]
            try:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, bufsize=1)
            except FileNotFoundError as e:
                raise RuntimeError(f"Could not launch {WHISPER_STREAM_BIN}: {e}")
            self.running = True
            self.error = None
            self.started_at = time.time()
            self.count = 0
            self._last_words = []
            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._translator = threading.Thread(target=self._translate_loop,
                                                daemon=True)
            self._reader.start()
            self._translator.start()

    def stop(self) -> None:
        with self._lock:
            self.running = False
            proc = self._proc
            self._proc = None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        self._utterances.put(None)  # unblock translator so it can exit

    def status(self) -> dict:
        return {
            "running": self.running,
            "error": self.error,
            "students": self.hub.subscriber_count(),
            "utterances": self.count,
            "model": STREAM_MODEL.name,
            "ollama_model": OLLAMA_MODEL,
            "uptime": round(time.time() - self.started_at) if self.started_at
                      and self.running else 0,
        }

    # -- worker threads --
    def _read_loop(self) -> None:
        proc = self._proc
        if not proc or not proc.stdout:
            return
        in_block = False
        parts: list[str] = []
        try:
            for raw in proc.stdout:
                if not self.running:
                    break
                line = raw.rstrip("\n")
                if "Transcription" in line and "START" in line:
                    in_block, parts = True, []
                    continue
                if "Transcription" in line and "END" in line:
                    in_block = False
                    text = " ".join(parts).strip()
                    if is_speech(text):
                        self._emit(text)
                    parts = []
                    continue
                if in_block:
                    m = _SEGMENT_RE.match(line)
                    seg = (m.group(1) if m else line).strip()
                    if is_speech(seg):
                        parts.append(seg)
        except (ValueError, OSError):
            pass
        finally:
            rc = proc.poll()
            if self.running and rc not in (0, None):
                err = ""
                try:
                    err = (proc.stderr.read() or "")[-500:] if proc.stderr else ""
                except Exception:
                    pass
                self.error = f"whisper-stream exited ({rc}). {err.strip()}"
            self.running = False

    def _emit(self, english: str) -> None:
        english = self._trim_overlap(english)
        if not english:
            return  # fully duplicated the previous utterance
        self._seq += 1
        self.count += 1
        self.last_utterance_at = time.time()
        seq = self._seq
        # Instant English-only event so the caption shows up right away.
        self.hub.publish({"seq": seq, "en": english, "zh": None, "vi": None,
                          "final": False, "t": round(self.last_utterance_at * 1000)})
        self._utterances.put((seq, english))

    def _trim_overlap(self, english: str) -> str:
        """Drop a leading run of words that merely repeats the tail of the
        previous utterance (VAD windows can overlap on continuous speech)."""
        words = english.split()
        prev = self._last_words
        max_k = min(len(words), len(prev), 12)
        best = 0
        for k in range(max_k, 0, -1):
            if [w.lower().strip(".,;:!?") for w in prev[-k:]] == \
               [w.lower().strip(".,;:!?") for w in words[:k]]:
                best = k
                break
        self._last_words = words
        return " ".join(words[best:]).strip()

    def _translate_loop(self) -> None:
        while True:
            item = self._utterances.get()
            if item is None:
                break
            seq, english = item
            translations = translate_all(english)
            self.hub.publish({
                "seq": seq, "en": english,
                "zh": translations.get("zh", ""), "vi": translations.get("vi", ""),
                "final": True, "t": round(time.time() * 1000),
            })
            if not self.running and self._utterances.empty():
                break


# --- Server-side TTS fallback (macOS `say`) ----------------------------------

def say_to_wav(text: str, lang: str, out_path: Path) -> Path:
    """Render text to a WAV using a built-in macOS voice (fallback for browsers
    that lack a Chinese/Vietnamese voice). Returns the output path."""
    meta = LANGUAGES.get(lang)
    if not meta:
        raise ValueError(f"Unknown language: {lang}")
    aiff = out_path.with_suffix(".aiff")
    subprocess.run(["say", "-v", meta["say_voice"], "-o", str(aiff), text],
                   check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(aiff), "-ar", "22050", "-ac", "1",
                    str(out_path)], check=True, capture_output=True)
    aiff.unlink(missing_ok=True)
    return out_path
