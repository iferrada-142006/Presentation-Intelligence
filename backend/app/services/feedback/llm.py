"""
LLM-based feedback generation via Claude Haiku.

Design principles:
- The LLM receives STRUCTURED DATA only (metrics + transcript text).
  It never receives the video or raw audio.
- Every feedback item must include an 'evidence' field citing a specific
  metric or transcript excerpt. The prompt enforces this.
- We distinguish observation (measured) from inference (interpreted).
  The prompt instructs the LLM to do the same.
- Output is validated: if JSON parsing fails, we return a safe fallback
  rather than crashing the pipeline.
- Prompt version is stored with every feedback item for reproducibility.
"""

import json
import logging
import re
import anthropic
from app.config import settings

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1.0"
LLM_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1800


def _build_prompt(data: dict, language: str) -> str:
    p = data["presentation"]
    m = data["metrics"]
    transcript = data["transcript_text"]

    lang_label = "Spanish" if language == "es" else "English"
    response_lang = "en español" if language == "es" else "in English"

    # Format metrics for the prompt clearly
    duration_min = round(p["duration_seconds"] / 60, 1) if p.get("duration_seconds") else "?"
    wpm_ref = "120–150 WPM is typical for presentations"

    metrics_block = f"""
SPEECH / AUDIO:
- Duration: {p.get('duration_seconds', '?')}s ({duration_min} min)
- Total words: {m.get('total_words', '?')}
- Average WPM: {m.get('avg_wpm', '?')} ({wpm_ref})
- Filler words detected: {m.get('filler_count', '?')} ({m.get('filler_rate_per_min', '?')}/min) [confidence: 0.7 — Whisper may miss some]
- Pauses ≥ 0.5s: {m.get('pause_count', '?')}
- Average pause duration: {m.get('avg_pause_duration', '?')}s
- Silence ratio: {round(float(m.get('silence_ratio', 0)) * 100, 1)}% of total time
- Speech rate variability (WPM std): {m.get('wpm_std', '?')} — lower = more stable rhythm
- Volume variability (energy CV): {round(float(m.get('energy_cv', 0)) * 100, 1)}% — higher = more dynamic
""".strip()

    # Append vision metrics if available (optional — only present for Phase 5+ jobs)
    vision_keys = ("face_visible_ratio", "head_yaw_mean", "head_yaw_std",
                   "head_pitch_mean", "head_forward_ratio", "body_movement_mean")
    if any(m.get(k) is not None for k in vision_keys):
        face_pct = round(float(m.get("face_visible_ratio", 0)) * 100, 1)
        forward_pct = round(float(m.get("head_forward_ratio", 0)) * 100, 1)
        metrics_block += f"""

BODY / HEAD (from video — confidence 0.75–0.9):
- Face visible: {face_pct}% of frames
- Head facing camera (|yaw|<20° AND |pitch|<20°): {forward_pct}% of time
- Head yaw mean ± std: {round(float(m.get('head_yaw_mean', 0)), 1)}° ± {round(float(m.get('head_yaw_std', 0)), 1)}°  [+ = turned right]
- Head pitch mean ± std: {round(float(m.get('head_pitch_mean', 0)), 1)}° ± {round(float(m.get('head_pitch_std', 0)), 1)}°  [+ = tilted down]
- Body movement mean: {round(float(m.get('body_movement_mean', 0)) * 100, 2)} (normalized ×100)"""

    # Timeline events block — only present for Phase 6+ jobs
    events = data.get("timeline_events", [])
    events_block = ""
    if events:
        lines = []
        for e in events[:20]:  # cap at 20 to stay within token budget
            ts = e.get("start_seconds", 0)
            m_val = int(ts) // 60
            s_val = int(ts) % 60
            lines.append(f"  [{m_val}:{s_val:02d}] {e.get('description', e.get('event_type'))}")
        events_block = "\n\nTIMELINE EVENTS (specific moments — use these to cite timestamps):\n" + "\n".join(lines)

    return f"""You are an evidence-based communication coach analyzing a {lang_label} presentation.

MEASURED DATA (objective):
{metrics_block}{events_block}

TRANSCRIPT:
{transcript}

INSTRUCTIONS:
1. Generate feedback {response_lang} based ONLY on the data above.
2. For each item, cite the specific metric, timestamp, or transcript quote that supports it.
3. Distinguish what was MEASURED from what you INFER. Use phrases like "the data shows", "this suggests", "one possible interpretation".
4. Do NOT use psychological labels: avoid words like "nervous", "insecure", "confident", "passionate".
5. Be specific and constructive. Reference timestamps (e.g., "at 1:23") when timeline events support the point.
6. Generate exactly 2–3 strengths, 2–3 improvements, and 2 exercises.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{{
  "strengths": [
    {{"content": "specific observation", "evidence": "metric or quote"}}
  ],
  "improvements": [
    {{"content": "specific observation", "evidence": "metric or quote"}}
  ],
  "exercises": [
    {{"content": "concrete exercise to practice"}}
  ]
}}"""


def generate(presentation_data: dict, language: str = "es") -> list[dict]:
    """
    Call Claude Haiku and return a list of feedback items ready to insert.

    Returns:
        List of dicts: {category, content, evidence, llm_model, llm_prompt_version}
    """
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping LLM feedback")
        return []

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = _build_prompt(presentation_data, language)

    logger.info(f"Calling {LLM_MODEL} for feedback ({len(prompt)} chars prompt)")
    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    logger.info(f"LLM response: {len(raw)} chars, "
                f"input_tokens={message.usage.input_tokens}, "
                f"output_tokens={message.usage.output_tokens}")

    # Extract JSON — Claude sometimes wraps it in ```json ... ```
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        logger.error(f"No JSON found in LLM response: {raw[:200]}")
        return []

    try:
        parsed = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e} — raw: {raw[:200]}")
        return []

    items = []
    for category in ("strengths", "improvements", "exercises"):
        for entry in parsed.get(category, []):
            items.append({
                "category": category[:-1],  # strength | improvement | exercise
                "content": entry.get("content", ""),
                "evidence": entry.get("evidence"),
                "llm_model": LLM_MODEL,
                "llm_prompt_version": PROMPT_VERSION,
            })

    logger.info(f"Generated {len(items)} feedback items")
    return items
