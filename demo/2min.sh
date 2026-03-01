#!/usr/bin/env bash
# Static demo splash screen — run in left 50% of terminal
# Right half shows live demo

clear

# Flame gradient logo
colors=(220 214 208 202 196 196)
i=0
echo ""
figlet -f slant "vibecheck" | while IFS= read -r line; do
  color=${colors[$i]}
  [ -z "$color" ] && color=196
  printf '\033[38;5;%dm%s\033[0m\n' "$color" "$line"
  ((i++))
done
printf '\033[1;37m  check your vibes from anywhere\033[0m\n'
printf '\033[38;5;250m  🔧 approve · 🎤 voice · 🌐 translate · 🔔 notify\033[0m\n'

echo ""
echo ""
#
# Tech stack
printf '\033[1;38;5;208m  STACK\033[0m\n'
echo ""
printf '\033[1;37m  Mistral Vibe · Python · FastAPI · Svelte · WebSocket · Vite PWA\033[0m\n'

echo ""
echo ""

# Architecture diagram
printf '\033[1;38;5;208m  ARCH\033[0m\n'
printf '\033[1;37m'
echo ""
cat <<'ARCH'
  Terminal (Textual TUI) ──┐
                           ├── same process, same AgentLoop
  Phone (PWA via WSS) ─────┘
ARCH
printf '\033[0m'

echo ""
echo ""

# Models used
printf '\033[1;38;5;208m  MODELS USED\033[0m\n'
echo ""
printf '\033[1;37m'
cat <<'MODELS'
  Devstral 2          Mistral Vibe
  Mistral Large V3    Translation, Visual Debugging
  Ministral 8B        Notification rewrites, urgency
  Voxtral Mini        ASR/TTS
  Silero (ONNX)       Local VAD
  ElevenLabs          TTS
MODELS
printf '\033[0m'


echo ""
echo ""

# Team
printf '\033[1;38;5;208m  TEAM SHISA\033[0m'
echo ""
printf '\033[0m  \033[1;37mAdam & Leonard\033[0m\n'


# Keep screen alive
read -r -s -n 1
