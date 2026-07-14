#!/usr/bin/env bash
#
# Start ClassCaption on your local network and open the teacher console.
# Students on the same Wi-Fi open the /student link shown below.
#
#   ./run.sh
#   PORT=8080 ./run.sh                 # custom port
#   VAD_THOLD=0.80 ./run.sh            # ignore quieter sound (fewer false lines)
#   OLLAMA_MODEL=gemma4 ./run.sh       # choose the translation model
#
set -euo pipefail

cd "$(dirname "$0")"
export PORT="${PORT:-5005}"
export HOST="0.0.0.0"                                          # share on the LAN
export STREAM_MODEL="${STREAM_MODEL:-$(pwd)/models/ggml-small.en.bin}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4}"

if [ ! -d ".venv" ]; then
  echo "No virtualenv found. Run ./install.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- Pre-flight checks ------------------------------------------------------
command -v whisper-stream >/dev/null \
  || { echo "❌ whisper-stream not found — run: brew install whisper-cpp"; exit 1; }
[ -f "$STREAM_MODEL" ] \
  || { echo "❌ Speech model missing: $STREAM_MODEL  (run ./install.sh)"; exit 1; }

# --- Ensure Ollama (the translator) is running ------------------------------
OLLAMA_STARTED=0
ollama_up() { curl -s "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; }
if ! command -v ollama >/dev/null 2>&1; then
  echo "⚠️  'ollama' not found — install from https://ollama.com (translations need it)."
elif ollama_up; then
  echo "✓ Ollama already running"
else
  echo "▶ Starting Ollama…"
  ollama serve > /tmp/ollama-serve.log 2>&1 &
  OLLAMA_PID=$!
  OLLAMA_STARTED=1
  for _ in $(seq 1 40); do ollama_up && break; sleep 0.5; done
  ollama_up && echo "✓ Ollama is up" \
            || echo "⚠️  Ollama didn't start in time — check /tmp/ollama-serve.log"
fi
cleanup() { [ "${OLLAMA_STARTED:-0}" = "1" ] && kill "${OLLAMA_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 127.0.0.1)"
echo ""
echo "  🎙️  ClassCaption is starting…"
echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │  Teacher console : http://${IP}:${PORT}/live"
echo "  │  Student link    : http://${IP}:${PORT}/student"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""

( sleep 1.5
  if command -v open >/dev/null 2>&1; then open "http://${IP}:${PORT}/live"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://${IP}:${PORT}/live"
  fi ) >/dev/null 2>&1 &

# Not `exec`, so the cleanup trap runs (and stops Ollama) when the app exits.
python app.py
