# Transcribe

Audio and video transcription with speaker identification — available as a **CLI tool**, **web app**, and **cross-platform desktop app**.

---

## Providers

| Provider | Tier | Price | Speaker ID | Languages |
|---|---|---|---|---|
| [AssemblyAI](https://assemblyai.com) | Freemium | $0.17 / hr · **$50 free credits** | ✅ With names | 99+ |
| [Deepgram Nova-3](https://deepgram.com) | Freemium | $0.26 / hr · **12 000 min / yr free** | ✅ Labels | 40+ |
| [OpenAI Whisper](https://platform.openai.com) | Paid | $0.18 – $0.36 / hr | ✗ | 99+ |
| Whisper (local) | **Free** | Free forever | ✗ | 99+ |

> **No upfront payment required** for AssemblyAI, Deepgram, or the local Whisper option.
> OpenAI requires a funded account but has no minimum spend.

---

## Features

- **Four transcription backends** — pick the right trade-off between cost, accuracy, and privacy
- **Speaker diarization** — AssemblyAI and Deepgram identify multiple speakers; AssemblyAI also detects speaker names from conversation context
- **Universal format pipeline** — any audio or video file is normalised to 16 kHz mono WAV before upload via ffmpeg
- **Real-time progress** — Server-Sent Events stream log lines to the UI as they happen
- **Markdown output** — timestamped `[HH:MM:SS] Speaker: text` format
- **Three usage modes** — CLI, web browser, and Electron desktop app
- **122 automated tests** — pytest suite covers all providers and edge cases

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/kneeraazon404/transcribe
cd transcribe

# 2. Configure
cp .env.example .env
# Edit .env — add at least one API key (or use --backend whisper for free local mode)

# 3. Install
make install

# 4-A. Run as web app (two terminals)
make dev-api      # FastAPI backend on :8000
make dev-web      # Next.js frontend on :3000

# 4-B. Run as desktop app
make dev          # Electron — starts both servers and opens the window
```

---

## Installation

### System dependencies

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows
winget install FFmpeg
```

### Python dependencies

```bash
uv venv
uv pip install --python .venv/bin/python -r requirements.txt
```

The local Whisper backend also requires:

```bash
uv pip install --python .venv/bin/python faster-whisper
```

### Frontend & Electron

```bash
cd frontend && npm install
cd electron && npm install
```

Or all at once with `make install`.

---

## Configuration

Copy `.env.example` to `.env` and fill in the keys for the providers you want:

```env
ASSEMBLYAI_API_KEY=   # https://assemblyai.com  — free $50 credits on sign-up
DEEPGRAM_API_KEY=     # https://deepgram.com    — 12 000 min/yr free tier
OPENAI_API_KEY=       # https://platform.openai.com — pay-per-use, no free tier
# Whisper (local) requires no key — install faster-whisper instead
```

The backend reports which providers are currently available at `GET /api/health`.

---

## Usage

### CLI

```bash
# Basic — saves transcript.md in the current directory
transcribe audio.mp3

# Choose backend
transcribe interview.mp4 --backend deepgram
transcribe meeting.mp4   --backend whisper --model small

# Full options
transcribe audio.mp3 \
  --backend assemblyai \
  --language es \
  --title "Team standup 2026-04-21" \
  --output ~/Documents/standup.md \
  --keep-wav
```

**Backends**

| Flag | Description |
|------|-------------|
| `assemblyai` | Cloud, speaker diarization + name detection, 99+ languages |
| `deepgram` | Cloud, fast, speaker labels, 40+ languages |
| `openai` | Cloud, GPT-4o powered, no diarization |
| `whisper` | Local, free, offline, no diarization |

**CLI options**

```
positional:
  input_file              Path to audio or video file

optional:
  -o, --output PATH       Output .md path (default: <filename>.md in cwd)
  -b, --backend NAME      assemblyai | openai | deepgram | whisper
  -m, --model NAME        Provider-specific model (see table below)
  -l, --language CODE     BCP-47 code e.g. en, es, fr. Default: auto-detect
  -t, --title TEXT        Markdown document title
      --keep-wav          Retain the normalised WAV file
```

**Model options per backend**

| Backend | Models |
|---------|--------|
| `assemblyai` | Universal (fixed — no selection) |
| `deepgram` | `nova-3` (default), `nova-2`, `enhanced`, `base` |
| `openai` | `gpt-4o-mini-transcribe` (default), `gpt-4o-transcribe`, `whisper-1` |
| `whisper` | `tiny`, `base` (default), `small`, `medium`, `large-v3-turbo` |

### Web app

```bash
make dev-api   # terminal 1
make dev-web   # terminal 2
```

Open `http://localhost:3000`, choose a provider, drag-and-drop your file.

### Desktop app (Electron)

```bash
make dev
```

Starts both servers and opens the Electron window automatically.

---

## Output format

```markdown
# Interview with Jordan

[00:00:13] Jordan: Hey, can you hear me okay?
[00:00:15] Lauren: Loud and clear. How are you?
[00:00:18] Jordan: Good, thanks. Let's get started.
[00:01:26] Speaker 1: So the main agenda today is...
```

- AssemblyAI detects real speaker names from conversation context
- Falls back to `Speaker 1`, `Speaker 2`, … when names cannot be detected
- Providers without diarization output all speech under `Speaker 1`

---

## Architecture

```
transcribe/
├── utilities_data/transcribe/   # Core transcription library (Python)
│   ├── media_probe.py           # ffprobe — detect streams, duration
│   ├── ffmpeg_audio.py          # Normalize any file → 16 kHz mono WAV
│   ├── format_md.py             # SpeakerTurn → Markdown renderer
│   ├── transcribe_aai.py        # AssemblyAI provider
│   ├── transcribe_openai.py     # OpenAI Whisper API provider
│   ├── transcribe_deepgram.py   # Deepgram REST API provider
│   └── transcribe_whisper.py    # faster-whisper local provider
│
├── backend/                     # FastAPI REST API
│   ├── main.py                  # Endpoints, job runner, SSE stream
│   └── jobs.py                  # Thread-safe in-memory job store
│
├── frontend/                    # Next.js 16 + Tailwind CSS
│   ├── public/logo.svg          # Shared logo / browser icon asset
│   └── app/components/
│       ├── TranscribeApp.tsx    # Root — state machine, provider cards
│       ├── DropZone.tsx         # Drag-and-drop file picker
│       ├── ProgressView.tsx     # Live SSE progress log
│       └── TranscriptView.tsx   # Copy / .md / .txt download
│
├── electron/                    # Electron cross-platform wrapper
│   ├── main.js                  # Spawns FastAPI + Next.js, opens window
│   └── preload.js               # Minimal context bridge
│
├── executable_scripts/transcribe  # CLI entry point
└── tests/                         # 122 pytest tests
```

### Request flow

```
Browser / Electron window
    │  POST /api/transcribe  (multipart form)
    ▼
Next.js rewrite proxy  →  FastAPI :8000
    │
    ├── ThreadPoolExecutor
    │       ├── probe_media()      — ffprobe
    │       ├── normalize_to_wav() — ffmpeg → 16 kHz WAV
    │       └── transcribe_*()     — provider API or local model
    │                   │
    │           SpeakerTurn list
    │                   │
    │           format_md.py  →  transcript.md
    │
    │  GET /api/jobs/{id}/events   (SSE — real-time progress)
    ◄── data: {"type":"message","text":"..."}
    │
    │  GET /api/jobs/{id}/transcript
    ◄── {"transcript": "# Title\n[00:00:00] ...", "filename": "..."}
```

---

## API reference

### API list

- `GET /api/health` — report backend readiness and available transcription providers
- `POST /api/transcribe` — upload a file and start a transcription job
- `GET /api/jobs/{id}` — poll job state, progress messages, and transcript status
- `GET /api/jobs/{id}/events` — stream live job progress over Server-Sent Events
- `GET /api/jobs/{id}/transcript` — fetch the completed Markdown transcript
- `DELETE /api/jobs/{id}` — delete a job and clean up temporary files

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Available backends and their readiness |
| `POST` | `/api/transcribe` | Upload file, start job → `{job_id}` |
| `GET` | `/api/jobs/{id}` | Poll status, messages, transcript |
| `GET` | `/api/jobs/{id}/events` | SSE real-time progress stream |
| `GET` | `/api/jobs/{id}/transcript` | Fetch completed transcript |
| `DELETE` | `/api/jobs/{id}` | Delete job and clean up temp files |

**POST `/api/transcribe` — form fields**

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `file` | file | — | Required. Any audio or video format |
| `backend` | string | `assemblyai` | `assemblyai` · `openai` · `deepgram` · `whisper` |
| `model` | string | provider default | Model name — see table above |
| `language` | string | `` | BCP-47 code. Empty = auto-detect |
| `title` | string | filename | Markdown heading for the transcript |

---

## Building for distribution

```bash
# Build Next.js production bundle
make build

# Cross-platform Electron distributables
cd electron
npm run dist:mac    # macOS  → dist/*.dmg
npm run dist:win    # Windows → dist/*.exe
npm run dist:linux  # Linux  → dist/*.AppImage
```

> **Note:** The desktop installer now ships the packaged Next.js server and will use a bundled
> Python virtualenv when one is available at build time. For the most portable installer, run
> `make install` before packaging so the Electron build can include `.venv`. ffmpeg is still
> required on the target machine.
>
> For deployed web builds, set `NEXT_PUBLIC_SITE_URL` so canonical URLs, Open Graph, and sitemap
> metadata resolve to your production domain instead of localhost.

---

## Supported formats

| Category | Formats |
|----------|---------|
| Audio | WAV · MP3 · FLAC · OGG · AAC · M4A · WMA |
| Video | MP4 · MOV · AVI · MKV · FLV · WebM · WMV |

Any format supported by ffmpeg works.

---

## Provider limits

| Provider | Max size | Max duration | Notes |
|---|---|---|---|
| AssemblyAI | 5 GB | 10 hours | Async cloud processing |
| Deepgram | 2 GB | — | Synchronous cloud |
| OpenAI | **25 MB** | ~13 min | Use AAI or Deepgram for longer files |
| Whisper (local) | RAM-bound | RAM-bound | Depends on hardware |

---

## License

Personal utilities — use at your own discretion.
