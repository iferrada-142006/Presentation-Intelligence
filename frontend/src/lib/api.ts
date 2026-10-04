const BASE = '/api'

export interface UploadResponse {
  id: number
  title: string
  status: string
  uploaded_at: string
  job_id: number
}

export interface JobStatus {
  id: number
  status: string
  current_stage: string | null
  progress_pct: number
  error_message: string | null
}

export interface StatusResponse {
  id: number
  title: string
  status: string
  duration_seconds: number | null
  uploaded_at: string
  processed_at: string | null
  job: JobStatus | null
}

export interface Metrics {
  // Speech / audio
  total_words: number | null
  avg_wpm: number | null
  filler_count: number | null
  filler_rate_per_min: number | null
  pause_count: number | null
  avg_pause_duration: number | null
  max_pause_duration: number | null
  pause_rate_per_min: number | null
  silence_ratio: number | null
  energy_cv: number | null
  wpm_std: number | null
  detected_language_prob: number | null
  // Vision (Phase 5+)
  face_visible_ratio: number | null
  head_yaw_mean: number | null
  head_yaw_std: number | null
  head_pitch_mean: number | null
  head_pitch_std: number | null
  head_forward_ratio: number | null
  body_movement_mean: number | null
  body_movement_std: number | null
}

export interface TranscriptSegment {
  start_seconds: number
  end_seconds: number
  text: string
  word_count: number
  confidence: number | null
}

export interface RubricScore {
  dimension: string
  score: number
  level: number
  level_label: string
  primary_metric: string | null
  primary_value: number | null
  evidence: string | null
}

export interface TimelineEvent {
  layer: 'audio' | 'speech' | 'vision'
  event_type: string
  start_seconds: number
  end_seconds: number | null
  duration_seconds: number | null
  magnitude: number | null
  description: string | null
}

export interface FeedbackItem {
  category: 'strength' | 'improvement' | 'exercise'
  content: string
  evidence: string | null
}

export interface Report {
  id: number
  title: string
  language: string
  status: string
  duration_seconds: number | null
  uploaded_at: string
  processed_at: string | null
  metrics: Metrics
  rubric: RubricScore[]
  transcript: TranscriptSegment[]
  timeline: TimelineEvent[]
  feedback: FeedbackItem[]
}

export async function uploadPresentation(
  file: File,
  title: string,
  language: string,
): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('title', title)
  form.append('language', language)
  const res = await fetch(`${BASE}/presentations/`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Upload failed')
  }
  return res.json()
}

export async function getStatus(id: number): Promise<StatusResponse> {
  const res = await fetch(`${BASE}/presentations/${id}/status`)
  if (!res.ok) throw new Error('Status fetch failed')
  return res.json()
}

export interface AudioFrame {
  t: number
  rms: number | null
  wpm: number | null
  silence: boolean
}

export interface VideoFrame {
  t: number
  yaw: number | null
  face: boolean
}

export interface ChartData {
  duration_seconds: number | null
  audio: AudioFrame[]
  video: VideoFrame[]
}

export function videoUrl(id: number): string {
  return `${BASE}/presentations/${id}/video`
}

export async function getChartData(id: number): Promise<ChartData> {
  const res = await fetch(`${BASE}/presentations/${id}/chart-data`)
  if (!res.ok) throw new Error('Chart data fetch failed')
  return res.json()
}

export async function getReport(id: number): Promise<Report> {
  const res = await fetch(`${BASE}/presentations/${id}/report`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Report fetch failed')
  }
  return res.json()
}
