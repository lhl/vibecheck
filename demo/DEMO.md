# vibecheck — check your vibes from anywhere — Demo Script & Setup

> **Last updated:** 2026-02-28
> **Hardware:** Linux desktop (Niri compositor) + Pixel 9 Android dev phone
> **Screen layout:** presenterm (terminal slides) → then 50% terminal / 50% scrcpy
> **Slides:** presenterm (primary, terminal-native) + Slidev PDF (backup/handout)

---

## Table of Contents

- [Equipment & Setup](#equipment--setup)
- [Screen Layout](#screen-layout)
- [Pre-Demo Checklist](#pre-demo-checklist)
- [Demo Scripts](#demo-scripts) (2-min video + 5-min live)
- [Fallback Plan](#fallback-plan)

---

## Equipment & Setup

### presenterm (Terminal Slides)

**Install on Arch Linux:**
```bash
sudo pacman -S presenterm
# or: cargo install presenterm
```

**Key features for Ghostty:**
- Inline images via Kitty graphics protocol (Ghostty supports this natively)
- Mermaid diagram rendering (renders to PNG → displays inline)
- Syntax-highlighted code blocks
- Speaker notes (visible in presenter mode)
- Seamless transition: quit slides → you're in the same terminal → run Vibe

**Create slides (3 slides max for the 5-min live):**
```markdown
---
title: vibecheck
theme:
  name: dark
---

<!-- Slide 1: ASCII Logo — hold for 10 seconds -->

```text
 ██▒   █▓ ██▓ ▄▄▄▄   ▓█████  ▄████▄   ██░ ██ ▓█████  ▄████▄   ██ ▄█▀
▓██░   █▒▓██▒▓█████▄ ▓█   ▀ ▒██▀ ▀█  ▓██░ ██▒▓█   ▀ ▒██▀ ▀█   ██▄█▒
 ▓██  █▒░▒██▒▒██▒ ▄██▒███   ▒▓█    ▄ ▒██▀▀██░▒███   ▒▓█    ▄  ▓███▄░
  ▒██ █░░░██░▒██░█▀  ▒▓█  ▄ ▒▓▓▄ ▄██▒░▓█ ░██ ▒▓█  ▄ ▒▓▓▄ ▄██▒▓██ █▄
   ▒▀█░  ░██░░▓█  ▀█▓░▒████▒▒ ▓███▀ ░░▓█▒░██▓░▒████▒▒ ▓███▀ ░▒██▒ █▄
   ░ ▐░  ░▓  ░▒▓███▀▒░░ ▒░ ░░ ░▒ ▒  ░ ▒ ░░▒░▒░░ ▒░ ░░ ░▒ ▒  ░▒ ▒▒ ▓▒
```

check your vibes from anywhere

<!-- end_slide -->

<!-- Slide 2: Problem (spoken, not much text on slide) -->

## the problem

your agent codes. then it stops and waits.
you've walked away.

<!-- end_slide -->

<!-- Slide 3: Architecture + Models (brief) -->

## how it works

![](./slides/architecture.png)

4 Mistral models + ElevenLabs TTS
**Devstral** codes · **Voxtral** STT · **Ministral** notifies · **Large** translates · **ElevenLabs** TTS

<!-- end_slide -->

<!-- Transition: press q, you're in the terminal → demo starts -->
```

Note: ASCII logo is a placeholder — replace with the actual generated logo. The logo should also appear in the PWA splash/header for brand consistency.

**Run:**
```bash
presenterm slides.md
# Arrow keys / space to navigate
# q to quit → seamless transition to live demo
```

**Generate diagrams for slides:**
```bash
# Architecture diagram → PNG for inline display
# Use Mermaid CLI, D2, or just create in any image editor
mmdc -i architecture.mmd -o slides/architecture.png -t dark -b transparent

# ANSI art title banner (optional, for extra flair)
toilet -f future "vibecheck" > slides/title.txt

# High-res logo → terminal display (if needed outside presenterm)
chafa --format kitty --size 60x30 vibecheck-logo.png
```

### Slidev (PDF Backup / Handout)

```bash
npm init slidev@latest  # one-time setup
# Write slides in slides.md (Slidev markdown format)
# Export:
npx slidev export --output slides-backup.pdf
```

Keep the Slidev version as a PDF backup in case presenterm has issues with the projector, and as a handout for judges.

---

### scrcpy (Android Screen Mirroring)

**Install on Arch Linux:**
```bash
sudo pacman -S scrcpy
```

**Connect Pixel 9:**
```bash
# USB (lowest latency, recommended for demo)
scrcpy --window-title="vibecheck" --window-borderless

# WiFi (if USB isn't practical on stage)
adb tcpip 5555
adb connect <phone-ip>:5555
scrcpy --window-title="vibecheck" --window-borderless
```

**Recommended scrcpy flags for demo:**
```bash
scrcpy \
  --window-title="vibecheck - Pixel 9" \
  --window-borderless \
  --max-size=1080 \
  --max-fps=60 \
  --video-bit-rate=8M \
  --no-audio \
  --stay-awake \
  --turn-screen-off  # keep phone screen off while mirroring, save battery
```

**Niri window placement:**
After launching scrcpy, use Niri's tiling to place:
- Left 50%: Terminal (SSH to EC2, Vibe running)
- Right 50%: scrcpy window (phone screen)

### Phone Prep (Pixel 9)

- [ ] PWA installed (Add to Home Screen from Chrome)
- [ ] Push notifications enabled (Chrome → vibecheck → Allow)
- [ ] Microphone permission granted
- [ ] Do Not Disturb OFF (need notification sounds for demo)
- [ ] Screen timeout set to 10 minutes (Settings → Display)
- [ ] Brightness at max (for scrcpy visibility)
- [ ] USB debugging enabled (Settings → Developer Options)
- [ ] USB cable connected and scrcpy tested

### EC2 Prep

- [ ] Vibe running and responsive
- [ ] `uv run vibecheck-vibe` running (Vibe TUI + vibecheck bridge on :7870)
- [ ] Caddy serving HTTPS (verify `https://your-domain` loads)
- [ ] WebSocket connectivity verified (phone connects, events flow)
- [ ] Test project loaded (something Vibe can code against)

---

## Screen Layout

### Phase 1: Presentation (100% terminal — presenterm)

```
┌────────────────────────────────────────────────────────────┐
│  Ghostty (fullscreen)                                      │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              presenterm slides.md                     │  │
│  │                                                       │  │
│  │     ╔═══════════════════════════════╗                 │  │
│  │     ║        vibecheck             ║                 │  │
│  │     ╚═══════════════════════════════╝                 │  │
│  │                                                       │  │
│  │     check your vibes from anywhere                    │  │
│  │                                                       │  │
│  │     [inline architecture diagram]                     │  │
│  │     (rendered via Kitty graphics)                     │  │
│  │                                                       │  │
│  │  ◀ ─────────────────────────────────────────────── ▶  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│   Intro → Problem → Architecture → Models → "let's demo"  │
│                                                            │
└────────────────────────────────────────────────────────────┘

  Press q → exits presenterm → you're in the terminal
  The transition to live demo is seamless
```

### Phase 2: Live Demo (50/50 split — Niri tiling)

```
┌────────────────────────────┬───────────────────────────────┐
│                            │                               │
│  TERMINAL (50%)            │  SCRCPY / PHONE (50%)         │
│  SSH into EC2              │  Pixel 9 via scrcpy           │
│  Vibe agent running        │  vibecheck PWA                │
│                            │                               │
│  $ vibecheck-vibe           │  ┌─────────────────────────┐  │
│  > I'll create a REST...   │  │ 🟢 Vibe Mobile    🔔 ⚙️│  │
│  > 🔧 bash: npm test       │  │                         │  │
│  > ⏳ Waiting for approval  │  │ Chat messages...        │  │
│                            │  │                         │  │
│                            │  │ ⚠️ APPROVE bash?        │  │
│                            │  │ [✅ Approve] [❌ Deny]  │  │
│                            │  │                         │  │
│                            │  │ [🎤] Type or speak [→]  │  │
│                            │  └─────────────────────────┘  │
│                            │                               │
└────────────────────────────┴───────────────────────────────┘

  Transition: resize Ghostty to 50%, open scrcpy alongside
  Or: Niri keybind to switch from fullscreen → tiled layout
```

---

## Pre-Demo Checklist

Run through this 10 minutes before presenting:

```bash
# 0. Test presenterm with projector
presenterm slides.md
# Verify: inline images render (Kitty protocol), text is readable at room distance
# Press q to exit

# 1. Verify EC2 is live
curl -s -H "X-PSK: $VIBECHECK_PSK" https://your-domain/api/state | jq .

# 2. Verify vibecheck server is running on EC2 (preferred: vibecheck-vibe)
ssh ec2 "pgrep -af 'vibecheck-vibe|vibecheck\\.launcher|python -m vibecheck'"

# 3. Launch scrcpy
scrcpy --window-title="vibecheck - Pixel 9" --window-borderless \
  --max-size=1080 --max-fps=60 --video-bit-rate=8M --no-audio --stay-awake

# 4. Open terminal, SSH into EC2
ssh ec2

# 5. On phone: open vibecheck PWA
# If prompted, enter the same PSK used in step 1.
# Verify: green 🟢 connected indicator
# Verify: can see any existing Vibe session events

# 6. Test quick approval cycle
# On EC2: trigger a tool call in Vibe
# On phone: approve from PWA → verify Vibe continues

# 7. Test voice
# On phone: hold mic → speak → verify transcription appears

# 8. Test push notification
# On phone: close PWA → trigger approval in Vibe
# Verify: phone buzzes with notification
```

---

## Demo Scripts

We have two deliverables: a **2-minute pre-recorded video** (submitted to hackiterate) and a **5-minute live presentation** (to jury). They share the same story arc but have very different pacing.

Each beat is annotated with the **judging criteria** it targets:
- **T** = Technicity (20%) — technical depth, architecture
- **C** = Creativity (20%) — novelty, originality
- **U** = Usefulness (20%) — real problem, would people use it
- **D** = Demo (20%) — presentation quality, wow factor
- **A** = Track Alignment (20%) — Mistral models, Vibe integration

---

### SCRIPT A: 2-Minute Video (hackiterate submission)

**Format:** Single continuous screen capture — 50/50 split the entire time. Left: terminal (logo/slides → Vibe). Right: scrcpy (phone). Voiceover narration.
**Pacing:** ~280 words total. Every second counts. No cuts or transitions.
**Goal:** "Stop scrolling" moment. Judges watch this cold, without us in the room.

**Screen layout (entire video):**
```
┌─────────────────────────┬──────────────────────────┐
│  TERMINAL (left 50%)    │  SCRCPY (right 50%)      │
│                         │  Phone showing vibecheck  │
│  Starts: ASCII logo +   │  PWA — live the whole     │
│  key points             │  time                     │
│                         │                           │
│  Then: Vibe running     │                           │
│  (clear logo, show      │                           │
│  agent output)          │                           │
└─────────────────────────┴──────────────────────────┘
```

#### V1. Logo + Hook [0:00–0:15] — C, U

Left: ASCII logo + key bullet points (tagline, model names, etc.).
Right: Phone showing vibecheck PWA — already connected, session visible.

> *"You vibecode. Your agent stops and waits for you. You've walked away. It just sits there."*

> *"vibecheck — mission control for your Vibe agents, right from your phone."*

(The logo sits on the left while the phone is already live on the right. Audience sees the product immediately.)

#### V2. Core Loop — Approve From Phone [0:15–0:50] — D, T, A

Left: Clear the logo, Vibe is now running — agent working on a task, output scrolling.
Right: Events stream to the phone in real time. Approval prompt appears. Tap Approve. Vibe continues on the left.

> *"Your agent writes code, runs tools — everything streams to your phone live. When it needs approval, tap. It keeps going. That's the loop."*

(Let the real-time streaming breathe for a few seconds. The responsiveness sells itself.)

#### V3. Voice Loop — Voxtral In, ElevenLabs Out [0:50–1:10] — D, C, A

Left: Vibe terminal continues.
Right: Tap mic on phone. Speak in Japanese: "テストを実行して". Voxtral transcribes → send. Vibe acts on the left. Response comes back → phone speaks it via ElevenLabs TTS.

> *"Full voice loop. Voxtral transcribes your voice in — ElevenLabs speaks the response back. Any language."*

#### V4. Push Notifications — Lock Screen Approval [1:10–1:30] — U, D

Left: Vibe terminal continues working.
Right: Close the PWA (swipe away). Vibe hits an approval. Phone buzzes. Notification: "bash wants to run npm test". Tap Approve from lock screen. Vibe continues.

> *"Close the app. Walk away. Your phone buzzes when the agent needs you. Approve from your lock screen."*

#### V5. Feature Montage + Close [1:30–1:50] — A, T, C

Left: Return to ASCII logo + key points (or keep Vibe running).
Right: Quick feature flashes on phone — session list with multiple agents, tap translate on a message (Japanese appears), intensity slider from Chill to Ralph.

> *"Multi-session. Japanese translation. Four Mistral models plus ElevenLabs TTS — Devstral codes, Voxtral transcribes, Ministral notifies, Mistral Large translates, and ElevenLabs speaks it all back to you in Japanese or English. vibecheck. Check your vibes from anywhere."*

**[END — ~1:50]** (10 seconds buffer)

**Criteria coverage:** U hit in V1, V4. D hit in V2, V3, V4. A hit in V1, V2, V3, V5 (Mistral models + ElevenLabs for voice prize). C hit in V1, V3, V5. T hit in V2, V5. All five covered, heaviest on the three the organizer emphasizes (U, D, C).

**Recording notes:**
- One take, one screen capture — no editing/cuts needed (though you can re-record)
- Start with logo already displayed + phone already connected before hitting record
- The left terminal transition (logo → Vibe output) is just clearing the screen / switching tmux panes
- Voiceover can be recorded live or dubbed after (dub is safer for pacing)

---

### SCRIPT B: 5-Minute Live Presentation (jury)

**Format:** Phase 1 slides (~60s, 3 slides max) → Phase 2 live demo (~180s) → Phase 3 stretch features + close (~60s).
**Pacing:** ~700 words spoken. Room for improvisation and audience reaction.
**Goal:** Theatrical, memorable. Judges are in the room — energy matters. **Demo-heavy.**

#### Phase 1: Slides (presenterm, 3 slides max) [0:00–1:00]

##### B1. Title Slide — ASCII Logo [0:00–0:10] — C, D

Slide: ASCII art vibecheck logo fills the terminal. Clean, bold, sets the tone.

(Let it land for a beat. The logo in a terminal is a vibe.)

> *"vibecheck."*

##### B2. The Problem [0:10–0:35] — U, C

> *"Raise your hand if you've done some vibecoding this weekend."*

(Pause for hands.)

> *"Me too. Here's the thing — your agent is coding, and then it stops. 'Can I run npm test?' And if you've walked away... it just sits there. Blocked. Waiting for you."*

> *"We got tired of being chained to our terminals. So we built vibecheck — mission control for your Vibe agents, from your phone."*

##### B3. Architecture + Models [0:35–0:55] — T, A

Slide: Architecture diagram (Phone → HTTPS → EC2 → vibecheck bridge → Vibe AgentLoop).
Below or next slide: Model list — one line each.

> *"We hook directly into Vibe's AgentLoop — typed events, clean callbacks, in-process. Four Mistral models plus ElevenLabs: Devstral codes, Voxtral transcribes your voice, Ministral writes smart notifications, Mistral Large translates — and ElevenLabs speaks it all back to you. Full voice loop."*

(Keep this tight — 20 seconds. The demo will show all of this working.)

##### B4. Transition [0:55–1:00] — D

> *"OK, let me show you."*

**Press q → exit presenterm → resize to 50/50 → scrcpy opens alongside terminal.**

(The seamless terminal-to-demo transition is itself a small wow moment.)

#### Phase 2: Live Demo [1:00–3:40]

This is the heart of the presentation. **2 minutes 40 seconds of live product.** Let it breathe.

##### B5. Core Loop — Approve From Phone [1:00–2:00] — D, U, T

1. Terminal (left): Vibe is running, working on a task.
2. Phone (right): Events stream in — assistant messages, tool calls appear in real time.
3. Vibe asks for approval → phone shows approval panel.
4. **Tap Approve on the phone → Vibe continues on terminal.**

> *"That's the core loop. Agent works, you approve from your pocket."*

(Let Vibe run for a beat so the audience sees multiple events streaming. The real-time feel is the demo moment — don't rush past it. If a second approval comes up naturally, approve it too.)

##### B6. Voice Loop — Voxtral STT + ElevenLabs TTS [2:00–2:40] — D, C, A

1. Tap mic on phone.
2. **Speak in Japanese:** "テストを実行して" (run the tests).
3. Voxtral transcribes → text appears → send.
4. Vibe receives the instruction and acts.
5. Agent response comes back → **phone reads it aloud via ElevenLabs TTS** (Japanese).

> *"Full voice loop. Voxtral transcribes your voice in — ElevenLabs speaks the response back out. Japanese, English, whatever you need."*

(The voice loop is the ElevenLabs prize moment. Make sure audio is audible to the room.)

##### B7. Push Notifications [2:40–3:15] — U, D

1. **Close the PWA** on the phone (swipe away — audience sees it disappear).
2. On terminal: Vibe hits a tool call that needs approval.
3. **Phone buzzes.** Notification appears on lock screen: "bash wants to run npm test".
4. Tap Approve from the notification.
5. Vibe continues.

> *"Close the app. Walk away. Your phone buzzes. Approve from your lock screen. Your agent never stops."*

##### B8. Translation [3:15–3:30] — A, C

Tap the translate toggle on a message. Japanese appears.

> *"One toggle — everything in Japanese. Mistral Large, code-aware. It knows not to translate your variable names."*

##### B9. Multi-Session [3:30–3:40] — C, U

Show the session switcher — 2-3 agents listed.

> *"And you're not limited to one agent. Mission control — switch between them, approve one, check on another."*

#### Phase 3: Close [3:40–4:50]

##### B10. Intensity (if audience energy is right) [3:40–3:55] — C

Show the intensity slider.

> *"How hard are you going? Chill... Locked In... Ralph. Named after Ralph Wiggum. Your agent won't stop and neither will your notifications."*

(Read the room — if time is tight or energy is winding down, skip this and go straight to QR.)

##### B11. QR Code + Close [3:55–4:30] — D

QR code on screen → the live URL. ASCII logo returns behind it.

> *"Want to try it? Pull out your phone."*

(Pause 10 seconds. Let people scan. Watch their faces when events appear on their phones.)

> *"You're watching the live session right now. That's vibecheck — check your vibes from anywhere."*

**[END — ~4:30]** (30 seconds buffer for applause / transition to Q&A)

**Criteria coverage:** U anchors the open (B2) and mid-demo (B5, B7). D is sustained through the entire live demo phase — 2:40 of pure product. A is woven throughout (architecture slide, Vibe hooks, Voxtral, translation). T lands in B3 and is visible in B5's real-time streaming. C hits in B1 (logo), B2 (novelty framing), B6 (Japanese voice), B9 (multi-session), B10 (intensity personality).

---

### Timing Cheat Sheet

| Beat | Video (2 min) | Live (5 min) | Primary Criteria |
|------|---------------|--------------|------------------|
| ASCII logo + key points | 15s (left side, phone live on right) | 10s (slide) | C, U |
| Problem statement | (in logo voiceover) | 25s | U, C |
| Architecture / Models | (on logo slide) | 20s (1 slide) | T, A |
| Transition to demo | clear left pane | 5s (quit presenterm) | D |
| **Core loop (approve from phone)** | **35s** | **60s** | **D, U, T** |
| **Voice in Japanese** | **20s** | **40s** | **D, C, A** |
| **Push notifications** | **20s** | **35s** | **U, D** |
| Translation | 5s (phone montage) | 15s | A, C |
| Multi-session | 5s (phone montage) | 10s | C, U |
| Intensity | 3s (phone montage) | 15s (optional) | C |
| Logo return + close | 7s | — | C |
| QR + close | — | 35s | D |
| **Total** | **~1:50** | **~4:30** | |
| **Demo time** | **~1:30 (75%)** | **~2:55 (65%)** | |

### Key Differences Between the Two Formats

| | 2-Min Video | 5-Min Live |
|---|---|---|
| **Layout** | 50/50 the entire time (single screen capture) | Fullscreen slides → 50/50 demo |
| **Slides** | Logo + key points on left terminal pane | 3 presenterm slides (logo, problem, arch) |
| **Demo time** | ~75% of runtime | ~65% of runtime |
| **Architecture** | Text on logo slide + voiceover | Slide with diagram, 20 seconds |
| **Transitions** | Just clear the left pane (no cuts) | quit presenterm → resize to 50/50 |
| **Audience interaction** | None (pre-recorded) | Hand raise, QR code, live reactions |
| **Translation** | Phone-side feature flash | Quick live tap (15s) |
| **Intensity/Multi-session** | Phone-side feature flash | Live if time allows |
| **ASCII logo** | Left pane at start + end | Opens slides, returns at QR close |
| **Tone** | Polished, tight, continuous | Theatrical, fun, conversational |
| **Biggest risk** | Not showing enough features | Running over time |
| **Mitigation** | Feature montage on phone at end | Know what to cut (intensity first) |
| **Recording** | One take, no editing needed | Live performance |

---

## Fallback Plan

| Failure | Mitigation |
|---------|------------|
| presenterm broken on projector | Switch to Slidev PDF backup (pre-exported) |
| EC2 down | Have a pre-recorded video of the full demo flow |
| scrcpy fails | Use Chrome DevTools mobile viewport on the projector instead |
| Phone won't connect | Demo from laptop browser in mobile mode |
| Voxtral API down | Type the message manually, explain voice would have worked |
| Push notifications don't fire | Show the notification in the PWA directly, explain push pipeline |
| WiFi unreliable at venue | USB tether phone to laptop, connect EC2 over phone's data |
| Vibe crashes mid-demo | Have a second session pre-loaded, `vibe --resume` |

### Pre-Record Backup

Before the hackathon presentation, record a complete screen capture of the full demo flow (all beats) as a fallback video. Use OBS or similar.

```bash
# Quick OBS recording setup (Wayland/Niri)
# Record the full 50/50 layout for 3-5 minutes
# Save as demo-backup.mp4
```

---

*See also: [PLAN.md](./PLAN.md) (implementation plan), [README.md](./README.md) (product brief)*
