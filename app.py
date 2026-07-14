"""ClassCaption — real-time lecture translation over the classroom Wi-Fi.

Your Mac listens to your lecture, transcribes your English speech (whisper.cpp),
translates each finalized sentence to Chinese & Vietnamese with a local LLM
(Ollama), and pushes captions to your students' phones over the LAN. Each phone
shows the caption and speaks it through the student's headphones. Everything runs
on-device — no audio leaves the room, no accounts, no internet required.

    Teacher console : /live      (start/stop, QR code, live feed)
    Student page    : /student   (pick language, read + hear the lecture)

Run with:  ./run.sh
"""

from __future__ import annotations

import json
import os
import queue
import socket
from pathlib import Path

import segno
from flask import (Flask, Response, jsonify, redirect, render_template, request,
                   send_file, abort)

import live as lv

app = Flask(__name__)

# One shared broadcast hub + pipeline for the whole server.
HUB = lv.Hub()
PIPELINE = lv.LivePipeline(HUB)

# On-demand server-side TTS clips (fallback for phones without a built-in voice).
TTS_DIR = lv.BASE_DIR / "uploads" / "tts"
TTS_DIR.mkdir(parents=True, exist_ok=True)


# --- Helpers -----------------------------------------------------------------

def get_lan_ip() -> str:
    """Best-effort local network IP (works offline; no packets are sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def server_port() -> int:
    return int(os.environ.get("PORT", "5005"))


# --- Routes ------------------------------------------------------------------

@app.route("/")
def home():
    return redirect("/live")


@app.route("/health")
def health():
    import shutil
    return jsonify({
        "whisper_stream": shutil.which(lv.WHISPER_STREAM_BIN) is not None,
        "stream_model": lv.STREAM_MODEL.exists(),
        "ollama": _ollama_up(),
        "ollama_model": lv.OLLAMA_MODEL,
    })


def _ollama_up() -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(f"{lv.OLLAMA_URL}/api/tags", timeout=2)
        return True
    except Exception:
        return False


@app.route("/live")
def live_console():
    """Teacher's control console: start/stop, status, and the student URL + QR."""
    ip = get_lan_ip()
    student_url = f"http://{ip}:{server_port()}/student"
    qr_svg = segno.make(student_url, error="m").svg_inline(scale=6, border=2)
    return render_template("live.html", student_url=student_url, ip=ip,
                           port=server_port(), qr_svg=qr_svg,
                           languages=lv.LANGUAGES)


@app.route("/student")
def student():
    """What students open on their phones: pick a language, read + hear captions."""
    return render_template("student.html", languages=lv.LANGUAGES)


@app.route("/live/start", methods=["POST"])
def live_start():
    try:
        PIPELINE.start()
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "status": PIPELINE.status()})


@app.route("/live/stop", methods=["POST"])
def live_stop():
    PIPELINE.stop()
    return jsonify({"ok": True, "status": PIPELINE.status()})


@app.route("/live/status")
def live_status():
    return jsonify(PIPELINE.status())


@app.route("/stream")
def stream():
    """Server-Sent Events: pushes caption events to every connected browser.

    One-directional, auto-reconnecting, plain HTTP -- exactly what a room full of
    receive-only student devices needs.
    """
    def gen():
        q = HUB.subscribe()
        try:
            for ev in HUB.history()[-8:]:
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            yield ": connected\n\n"
            while True:
                try:
                    ev = q.get(timeout=15)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            HUB.unsubscribe(q)

    resp = Response(gen(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Connection"] = "keep-alive"
    return resp


@app.route("/say")
def say():
    """Server-side TTS fallback for phones lacking a Chinese/Vietnamese voice."""
    text = (request.args.get("text") or "").strip()
    lang = request.args.get("lang", "")
    if not text or lang not in lv.LANGUAGES:
        abort(400)
    key = f"{lang}_{abs(hash(text))}"
    out = TTS_DIR / f"{key}.wav"
    if not out.exists():
        try:
            lv.say_to_wav(text[:400], lang, out)
        except Exception:
            abort(500)
    return send_file(out, mimetype="audio/wav")


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = server_port()
    if host != "127.0.0.1":
        ip = get_lan_ip()
        print("\n  ClassCaption is sharing on your network:")
        print(f"    Teacher console : http://{ip}:{port}/live")
        print(f"    Student link    : http://{ip}:{port}/student\n")
    app.run(host=host, port=port, debug=False, threaded=True)
