# Presentation Intelligence

A multimodal AI platform that analyzes recorded presentations and delivers evidence-based feedback on communication effectiveness.

## Core Principle

The system strictly separates:
- **Observation** — what can be measured (WPM, pause duration, head orientation, energy)
- **Inference** — interpretations based on observations (with explicit caveats)
- **Evaluation** — scoring against an explicit rubric

No feedback is generated without traceable evidence.

## MVP

Upload a recorded presentation video → receive a multimodal analysis report with:
- Speech metrics (WPM, pauses, filler words)
- Audio features (energy, rhythm)
- Computer vision features (head pose, gaze estimate, movement)
- Interactive timeline with timestamped events
- LLM-generated feedback grounded in measured data

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Worker | Python async worker (job queue via PostgreSQL) |
| Database | PostgreSQL 16 |
| Speech-to-Text | faster-whisper (small model) |
| Computer Vision | MediaPipe |
| Audio Analysis | librosa |
| LLM Feedback | Anthropic Claude (Haiku) |
| Frontend | React + Vite + TypeScript + shadcn/ui |
| Infrastructure | Docker Compose + Nginx on Hetzner CX33 |

## Project Structure

```
presentation-intelligence/
├── backend/
│   ├── app/
│   │   ├── models/         SQLAlchemy models
│   │   ├── schemas/        Pydantic schemas
│   │   ├── routers/        FastAPI routers
│   │   ├── services/       Processing pipeline
│   │   │   ├── extraction/ ffmpeg audio/video extraction
│   │   │   ├── speech/     faster-whisper transcription
│   │   │   ├── audio/      librosa analysis
│   │   │   ├── video/      MediaPipe analysis
│   │   │   ├── analytics/  Feature engine
│   │   │   ├── rubric/     Rubric evaluation
│   │   │   └── feedback/   LLM feedback generation
│   │   └── worker/         Async job processing
│   └── tests/
├── frontend/               React + Vite app
├── docs/                   Architecture, methodology, decisions
└── nginx/                  Reverse proxy config
```

## Docs

- [Architecture](docs/architecture.md)
- [Methodology](docs/methodology.md)
- [Data Model](docs/data-model.md)
- [Decisions](docs/decisions.md)
- [Roadmap](docs/roadmap.md)

## Development Status

- [x] Phase 0 — Infrastructure
- [ ] Phase 1 — Video ingestion + job tracking
- [ ] Phase 2 — Speech pipeline (faster-whisper)
- [ ] Phase 3 — Audio analysis (librosa)
- [ ] Phase 4 — First functional report (MVP)
- [ ] Phase 5 — Computer Vision (MediaPipe)
- [ ] Phase 6 — Feature Engine + Timeline
- [ ] Phase 7 — Full dashboard
- [ ] Phase 8 — Rubric Engine
- [ ] Phase 9 — LLM Feedback (structured + traceable)
