#!/usr/bin/env bash
# Single-screen banner for the 2-min video left pane.
# Rendered by presenterm via +exec_replace, or run standalone.
# Flame gradient: yellow 220 → orange 214 → 208 → 202 → red 196

# --- Logo (figlet slant, flame gradient) ---
colors=(220 214 208 202 196 196)
i=0
figlet -f slant "vibecheck" | while IFS= read -r line; do
  color=${colors[$i]}
  [ -z "$color" ] && color=196
  printf '\033[38;5;%dm%s\033[0m\n' "$color" "$line"
  ((i++))
done

# --- Tagline ---
printf '\033[38;5;245m        check your vibes from anywhere\033[0m\n'
echo ""

# --- Architecture one-liner ---
printf '\033[38;5;208m  Phone\033[38;5;245m ─── WSS ───▶ \033[38;5;208mvibecheck bridge\033[38;5;245m ───▶ \033[38;5;141mVibe AgentLoop\033[0m\n'
printf '\033[38;5;240m                    in-process · typed events · no terminal scraping\033[0m\n'
printf '\033[38;5;240m                    no upstream changes to Vibe\033[0m\n'
echo ""

# --- Feature bullets (dim white, orange icons) ---
printf '\033[38;5;208m  🔧\033[38;5;252m  Approve tool calls from your phone\033[0m\n'
printf '\033[38;5;208m  🎤\033[38;5;252m  Voice loop — Voxtral STT in, ElevenLabs TTS out\033[0m\n'
printf '\033[38;5;208m  🔔\033[38;5;252m  Push notifications — Ministral smart copy\033[0m\n'
printf '\033[38;5;208m  🌐\033[38;5;252m  EN↔JA translation — Mistral Large\033[0m\n'
printf '\033[38;5;208m  📡\033[38;5;252m  Multi-session fleet control\033[0m\n'
echo ""

# --- Model bar ---
printf '\033[38;5;240m  ─────────────────────────────────────────────────\033[0m\n'
printf '\033[38;5;208m  Devstral\033[38;5;245m · \033[38;5;208mVoxtral\033[38;5;245m · \033[38;5;208mMinistral\033[38;5;245m · \033[38;5;208mMistral Large\033[38;5;245m · \033[38;5;81mElevenLabs\033[0m\n'
