# Presentation Intelligence — Estado de avance
**Última actualización:** 2026-10-04  
**Repositorio:** https://github.com/iferrada-142006/Presentation-Intelligence  
**VPS:** pi.ferzamedia.com (Hetzner CX33 — 4 vCPU, 8 GB RAM)  
**Stack en producción:** FastAPI + PostgreSQL + React/Vite — systemd (sin Docker)

---

## Resumen ejecutivo

Pipeline multimodal completo end-to-end que:
1. Acepta un video de presentación vía upload
2. Lo procesa en background (6 etapas) produciendo ~40 métricas + eventos de timeline
3. Genera retroalimentación basada en evidencia usando Claude Haiku
4. Sirve un reporte completo vía API REST y UI React

**URL en producción:** https://pi.ferzamedia.com

---

## Fases completadas

### Phase 0 — Infraestructura
- VPS reescalado a CX33 (4 vCPU, 8 GB RAM, +2 GB swap)
- PostgreSQL, Python 3.12, Node 20 instalados
- DNS `pi.ferzamedia.com` → VPS
- SSL via Let's Encrypt + Nginx reverse proxy
- Repositorio GitHub con SSH key auth

### Phase 1 — Backend base
- FastAPI 0.115 con SQLAlchemy 2.0 y Alembic
- Esquema de DB: 8 tablas (ver sección Datos)
- Upload endpoint con validación de extensión y límite de tamaño (512 MB)
- Worker de background con polling PostgreSQL (no Redis — ADR-001)
- Systemd services: `pi-api` (2 workers Uvicorn) y `pi-worker`
- Nginx: `/api/` → FastAPI, `/` → frontend estático

### Phase 2 — Speech Analysis
- **faster-whisper** (int8, CPU) para STT — modelo `small`
- Transcripción con timestamps por palabra (words_json en DB)
- Detección de muletillas (FILLERS_ES + FILLERS_EN) con bigrams
- Métricas: `total_words`, `avg_wpm`, `filler_count`, `filler_rate_per_min`
- Confianza 0.7 para fillers (Whisper normaliza el habla)

### Phase 3 — Audio Analysis
- **librosa** para análisis frame-level (window=0.5s, hop=0.25s)
- Umbral de silencio dinámico: `mean(voiced_rms) * 0.15` (percentile-based)
- Detección de pausas ≥ 0.5s
- WPM local por frame (desde timestamps de Whisper)
- Métricas: `pause_count`, `avg_pause_duration`, `max_pause_duration`, `pause_rate_per_min`, `silence_ratio`, `energy_cv`, `wpm_std`
- `audio_features` table: una fila por frame (~4fps)

### Phase 4 — Frontend MVP + LLM Feedback
- **Claude Haiku** (`claude-haiku-4-5-20251001`) para retroalimentación
  - Prompt enforce: sin etiquetas psicológicas, evidencia obligatoria
  - Versión de prompt almacenada en DB para reproducibilidad
- Endpoint `GET /api/presentations/{id}/report` con respuesta completa
- **React 18 + Vite 5 + TypeScript + Tailwind CSS**
- `HomePage`: drag-and-drop upload + polling de progreso
- `ReportPage`: métricas, feedback, transcripción

### Phase 5 — Computer Vision
- **MediaPipe** 0.10.18 + OpenCV headless 4.10
- Sampling a 2fps (offline, CPU)
- Head pose via PnP con 6 landmarks de FaceMesh (yaw, pitch, roll en grados)
- Body movement via landmarks de hombros/caderas entre frames
- Métricas: `face_visible_ratio`, `head_yaw_mean/std`, `head_pitch_mean/std`, `head_forward_ratio`, `body_movement_mean/std`
- `video_features` table: una fila por frame muestreado

### Phase 6 — Feature Engine (Timeline Events)
- Servicio `features/engine.py` que procesa features almacenadas → eventos semánticos
- 6 tipos de eventos con start/end/magnitude/description:
  - `pause`: silencio ≥ 1.5s (capa audio)
  - `wpm_sprint`: PPM > max(165, media+1.5σ) por ≥ 4s (audio)
  - `filler_cluster`: ≥ 3 muletillas en 30s (speech)
  - `head_away`: |yaw|>35° o |pitch|>25° por ≥ 2s (vision)
  - `face_absent`: cara no detectada ≥ 5s (vision)
  - `movement_spike`: body_movement > media+2.5σ (vision)
- Eventos incluidos en prompt LLM para feedback con timestamps específicos
- `timeline_events` table en DB
- Frontend: sección de línea de tiempo con timecodes, badges por capa, íconos

---

## Pipeline completo (6 etapas)

```
upload → [extract 5→15%] → [speech 20→55%] → [audio 58→72%]
       → [vision 73→83%] → [features 84→87%] → [feedback 88→95%] → 100%
```

| Etapa    | Servicio                        | Output                          |
|----------|---------------------------------|---------------------------------|
| extract  | ffmpeg (subprocess)             | metadata + WAV                  |
| speech   | faster-whisper (int8)           | TranscriptSegment + fillers     |
| audio    | librosa                         | AudioFeature rows + métricas    |
| vision   | MediaPipe FaceMesh+Pose         | VideoFeature rows + métricas    |
| features | engine.py (puro Python)         | TimelineEvent rows              |
| feedback | Claude Haiku API                | FeedbackItem rows               |

---

## Esquema de base de datos

```
presentations          (id, title, language, status, duration_seconds, ...)
video_files            (presentation_id, file_path, audio_path, fps, resolution, ...)
processing_jobs        (presentation_id, status, current_stage, progress_pct, ...)
transcript_segments    (presentation_id, start_seconds, end_seconds, text, words_json, ...)
presentation_metrics   (presentation_id, metric_name, value, unit, confidence)
audio_features         (presentation_id, timestamp_seconds, energy_rms, is_silence, local_wpm)
video_features         (presentation_id, timestamp_seconds, face_detected, head_yaw, head_pitch, body_movement)
timeline_events        (presentation_id, layer, event_type, start_seconds, end_seconds, magnitude, description)
feedback_items         (presentation_id, category, content, evidence, llm_model, llm_prompt_version)
```

**Migraciones Alembic (en orden):**
1. `cecadcc8d8ce` — initial schema
2. `c7468a82a15d` — add feedback_items
3. `a1f3b2c4d5e6` — add video_features
4. `b2e4f6a8c0d1` — add timeline_events

---

## API endpoints activos

```
POST   /api/presentations/              Upload video → crea job
GET    /api/presentations/              Lista todas
GET    /api/presentations/{id}/status   Estado + progreso del job
GET    /api/presentations/{id}/report   Reporte completo (métricas + timeline + feedback + transcript)
```

---

## Archivos clave

| Archivo | Descripción |
|---------|-------------|
| `/opt/presentation-intelligence/.env` | Credenciales (no en git) |
| `/opt/presentation-intelligence/backend/app/config.py` | Settings (pydantic-settings) |
| `/opt/presentation-intelligence/backend/app/worker/pipeline.py` | Orquestador de etapas |
| `/opt/presentation-intelligence/backend/app/services/speech/transcriber.py` | faster-whisper |
| `/opt/presentation-intelligence/backend/app/services/audio/analyzer.py` | librosa |
| `/opt/presentation-intelligence/backend/app/services/vision/analyzer.py` | MediaPipe |
| `/opt/presentation-intelligence/backend/app/services/features/engine.py` | Feature engine |
| `/opt/presentation-intelligence/backend/app/services/feedback/llm.py` | Claude Haiku |
| `/opt/presentation-intelligence/frontend/src/pages/HomePage.tsx` | Upload UI |
| `/opt/presentation-intelligence/frontend/src/pages/ReportPage.tsx` | Reporte UI |
| `/etc/nginx/sites-available/pi` | Nginx config (SSL, proxy) |
| `/etc/systemd/system/pi-api.service` | API service |
| `/etc/systemd/system/pi-worker.service` | Worker service |

---

## Principios de diseño (no negociables)

1. **Sin inferencia sin evidencia** — cada ítem de feedback cita métrica o timestamp
2. **Sin etiquetas psicológicas** — prohibido: nervioso, inseguro, confiado, apasionado
3. **Jerarquía OBSERVACIÓN / INFERENCIA / EVALUACIÓN** — claramente separadas
4. **No PII innecesario** — no reconocimiento facial, no biometría de identidad
5. **CPU-only** — int8 Whisper, MediaPipe CPU, sin GPU requerida

---

## Pendiente (fases futuras)

| Fase | Descripción |
|------|-------------|
| **7** | Dashboard interactivo — video player + charts sincronizados + timeline clickeable |
| 8 | Rubric Engine — dimensiones formales con definiciones y scoring |
| 9 | Feedback estructurado con trazabilidad completa evidencia→insight |
| 10 | Análisis de slides (si hay screenshare) |
| 11 | Comparación longitudinal entre sesiones |
| 12 | Validación humana y calibración |

---

## Notas técnicas

- **numpy float64 → DB**: todos los valores de faster-whisper/librosa requieren `float()` explícito antes del insert
- **MediaPipe + numpy 2.x**: funciona a pesar del warning de incompatibilidad
- **opencv-contrib-python conflicto**: instalar `opencv-python-headless` DESPUÉS de `mediapipe` y remover contrib
- **PostgreSQL job queue**: `WITH FOR UPDATE SKIP LOCKED` elimina necesidad de Redis (ADR-001)
- **Venv location**: `/opt/presentation-intelligence/.venv/` (no dentro de `/backend/`)
- **Build frontend**: `cd /opt/presentation-intelligence/frontend && npm run build`, deploy a `/var/www/presentation-intelligence/`
