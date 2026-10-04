# Architecture Decision Records

## ADR-001 — PostgreSQL como job queue (sin Redis en MVP)

**Decisión**: Usar una tabla `processing_jobs` en PostgreSQL como cola de trabajos en lugar de Redis + Celery.

**Alternativas**: Redis + Celery, ARQ, RQ, Dramatiq.

**Razón**: PostgreSQL ya existe en el VPS. Agregar Redis introduce otro servicio y dependencia para funcionalidad que una tabla con polling simple puede cubrir en el MVP. El sistema procesa un job a la vez (constraint de CPU/RAM), por lo que una cola sofisticada no agrega valor todavía.

**Trade-offs**: Polling cada N segundos introduce latencia mínima. Si el sistema escala a múltiples workers concurrentes, migrar a Redis+Celery es un cambio bien acotado.

---

## ADR-002 — faster-whisper en lugar de openai-whisper

**Decisión**: Usar `faster-whisper` (CTranslate2) para transcripción en lugar de `openai-whisper`.

**Alternativas**: openai-whisper (ya instalado), OpenAI Whisper API ($0.006/min).

**Razón**: faster-whisper es 2–4× más rápido en CPU con el mismo modelo (small), usa ~40% menos RAM, y tiene mejor integración con timestamps a nivel de palabra. No hay desventaja técnica para este uso.

**Trade-offs**: Dependencia adicional. La API de OpenAI elimina el problema de velocidad pero introduce costo y privacidad de datos.

---

## ADR-003 — React + Vite en lugar de Next.js

**Decisión**: Frontend con React + Vite + TypeScript + shadcn/ui.

**Alternativas**: Next.js, Remix, SvelteKit.

**Razón**: El dashboard es una app privada de usuario autenticado. No necesita SSR para SEO, ni generación estática. Los archivos estáticos de Vite se sirven directamente desde Nginx. Next.js agrega complejidad sin beneficio concreto para este caso.

**Trade-offs**: Sin SSR. Si en el futuro se quiere una landing page pública indexable, se puede agregar como proyecto separado o migrar.

---

## ADR-004 — Separación observación / inferencia / evaluación

**Decisión**: El sistema nunca convierte directamente una señal observable en una conclusión psicológica o de personalidad.

**Razón**: Rigor metodológico y honestidad epistémica. Las métricas de CV, audio y NLP tienen limitaciones técnicas que deben ser comunicadas explícitamente.

**Aplicación**: Cada `feedback_item` y `rubric_evaluation` en la base de datos incluye los campos `evidence_json` y `limitations_note`. El frontend debe mostrar siempre la métrica de origen junto a la interpretación.

---

## ADR-005 — Claude Haiku para feedback LLM

**Decisión**: Usar Claude Haiku (claude-haiku-4-5) como modelo LLM para generación de feedback.

**Alternativas**: Claude Sonnet, GPT-4o, modelos open-source locales.

**Razón**: El feedback LLM recibe datos estructurados (métricas + transcripción resumida), no video crudo. Haiku es suficientemente capaz para esta tarea. Costo estimado: <$0.003 por presentación. El sistema nunca envía el video al LLM.

**Trade-offs**: Menor capacidad de razonamiento que Sonnet. Si la calidad del feedback resulta insuficiente, cambiar a Sonnet es un cambio de una línea.
