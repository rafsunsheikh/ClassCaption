#!/usr/bin/env bash
#
# One-time setup for ClassCaption.
#   - installs system dependencies (whisper.cpp, ffmpeg) via Homebrew
#   - creates a Python virtualenv and installs Python deps
#   - downloads the small English speech model (~465 MB)
#
# Ollama (the translator) is installed separately from https://ollama.com
#
set -euo pipefail
cd "$(dirname "$0")"

bold() { printf "\033[1m%s\033[0m\n" "$*"; }

bold "==> 1/4  System dependencies (Homebrew)"
if command -v brew >/dev/null 2>&1; then
  brew list whisper-cpp >/dev/null 2>&1 || brew install whisper-cpp
  brew list ffmpeg      >/dev/null 2>&1 || brew install ffmpeg
  brew list sdl2        >/dev/null 2>&1 || brew install sdl2   # mic capture for whisper-stream
else
  echo "  Homebrew not found. Install from https://brew.sh, then re-run." >&2
  exit 1
fi

bold "==> 2/4  Python virtualenv"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "    venv ready (.venv)"

bold "==> 3/4  Speech model (small.en, ~465 MB)"
mkdir -p models
MODEL="models/ggml-small.en.bin"
if [ -f "$MODEL" ]; then
  echo "    $MODEL already present — skipping"
else
  curl -L --fail --progress-bar -o "$MODEL" \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin"
fi

bold "==> 4/4  Translator (Ollama)"
if command -v ollama >/dev/null 2>&1; then
  echo "    Ollama found. Pull a translation model if you haven't:  ollama pull gemma4"
else
  echo "    Ollama NOT found. Install from https://ollama.com, then:  ollama pull gemma4"
fi

bold "✅ Install complete."
echo "Start ClassCaption with:  ./run.sh"
