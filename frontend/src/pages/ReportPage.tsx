import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getReport, Report, RubricScore, TimelineEvent } from '../lib/api'

function fmt(v: number | null, decimals = 1): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(decimals)
}

function MetricCard({ label, value, unit, note }: {
  label: string
  value: string
  unit?: string
  note?: string
}) {
  return (
    <div className="bg-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">
        {value}
        {unit && <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>}
      </p>
      {note && <p className="text-xs text-gray-500 mt-1">{note}</p>}
    </div>
  )
}

function FeedbackSection({ items, category, title, color }: {
  items: Report['feedback']
  category: string
  title: string
  color: string
}) {
  const filtered = items.filter(i => i.category === category)
  if (!filtered.length) return null
  return (
    <div>
      <h3 className={`text-sm font-semibold uppercase tracking-wide mb-3 ${color}`}>{title}</h3>
      <div className="space-y-3">
        {filtered.map((item, i) => (
          <div key={i} className="bg-gray-800 rounded-xl p-4">
            <p className="text-gray-200 text-sm">{item.content}</p>
            {item.evidence && (
              <p className="text-xs text-gray-500 mt-2 border-l-2 border-gray-600 pl-3">
                {item.evidence}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

const DIMENSION_LABELS: Record<string, string> = {
  verbal_rhythm:       'Ritmo Verbal',
  filler_density:      'Muletillas',
  silence_management:  'Gestión del Silencio',
  vocal_dynamics:      'Dinámica Vocal',
  visual_presence:     'Presencia Visual',
}

const LEVEL_COLORS = [
  'bg-red-900 text-red-300 border-red-700',
  'bg-orange-900 text-orange-300 border-orange-700',
  'bg-yellow-900 text-yellow-300 border-yellow-700',
  'bg-blue-900 text-blue-300 border-blue-700',
  'bg-emerald-900 text-emerald-300 border-emerald-700',
]
const BAR_COLORS = ['#7f1d1d', '#7c2d12', '#78350f', '#1e3a5f', '#064e3b']

function RubricCard({ r }: { r: RubricScore }) {
  const label = DIMENSION_LABELS[r.dimension] ?? r.dimension
  const barColor = BAR_COLORS[r.level] ?? '#374151'
  const levelCls = LEVEL_COLORS[r.level] ?? LEVEL_COLORS[0]
  return (
    <div className="bg-gray-800 rounded-xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-white">{label}</p>
        <span className={`text-xs px-2 py-0.5 rounded border flex-shrink-0 ${levelCls}`}>
          {r.level_label}
        </span>
      </div>
      {/* Score bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-gray-500">
          <span>0</span>
          <span className="text-white font-bold text-sm">{r.score.toFixed(0)}</span>
          <span>100</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-2">
          <div
            className="h-2 rounded-full transition-all"
            style={{ width: `${r.score}%`, backgroundColor: barColor }}
          />
        </div>
      </div>
      {r.evidence && (
        <p className="text-xs text-gray-500 leading-relaxed">{r.evidence}</p>
      )}
    </div>
  )
}

const LAYER_COLORS: Record<string, string> = {
  audio:  'bg-blue-900 text-blue-300',
  speech: 'bg-purple-900 text-purple-300',
  vision: 'bg-teal-900 text-teal-300',
}

const EVENT_ICONS: Record<string, string> = {
  pause:           '⏸',
  wpm_sprint:      '⚡',
  filler_cluster:  '💬',
  head_away:       '↩️',
  face_absent:     '👻',
  movement_spike:  '🌊',
}

function tc(s: number): string {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

function TimelineRow({ evt }: { evt: TimelineEvent }) {
  const layerCls = LAYER_COLORS[evt.layer] ?? 'bg-gray-700 text-gray-300'
  const icon = EVENT_ICONS[evt.event_type] ?? '•'
  return (
    <div className="flex items-start gap-3 bg-gray-900 rounded-lg px-4 py-2.5 text-sm">
      <span className="font-mono text-gray-500 w-12 flex-shrink-0 pt-0.5">{tc(evt.start_seconds)}</span>
      <span className="text-base flex-shrink-0">{icon}</span>
      <p className="text-gray-300 flex-1">{evt.description ?? evt.event_type}</p>
      <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${layerCls}`}>
        {evt.layer}
      </span>
    </div>
  )
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    getReport(Number(id))
      .then(setReport)
      .catch(e => setError((e as Error).message))
  }, [id])

  if (error) {
    return (
      <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-red-400">{error}</p>
          <Link to="/" className="text-indigo-400 text-sm hover:underline">← Volver al inicio</Link>
        </div>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <p className="text-gray-400 animate-pulse">Cargando reporte…</p>
      </div>
    )
  }

  const { metrics: m, rubric, transcript, timeline, feedback } = report
  const durationMin = report.duration_seconds ? (report.duration_seconds / 60).toFixed(1) : '—'
  const silencePct = m.silence_ratio != null ? (m.silence_ratio * 100).toFixed(1) : '—'
  const energyCvPct = m.energy_cv != null ? (m.energy_cv * 100).toFixed(1) : '—'

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 py-10 px-4">
      <div className="max-w-4xl mx-auto space-y-10">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex gap-4 mb-2">
              <Link to="/" className="text-indigo-400 text-sm hover:underline">
                ← Nueva presentación
              </Link>
              <Link to={`/dashboard/${report.id}`} className="text-emerald-400 text-sm hover:underline">
                Ver dashboard ▶
              </Link>
            </div>
            <h1 className="text-2xl font-bold text-white">{report.title}</h1>
            <p className="text-gray-500 text-sm mt-1">
              {report.language === 'es' ? 'Español' : 'English'} · {durationMin} min ·{' '}
              {new Date(report.processed_at ?? report.uploaded_at).toLocaleDateString('es-CL')}
            </p>
          </div>
          <span className="px-3 py-1 text-xs rounded-full bg-emerald-900 text-emerald-300 font-medium">
            Completo
          </span>
        </div>

        {/* Metrics Grid */}
        <section>
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
            Voz y audio
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            <MetricCard label="Duración" value={durationMin} unit="min" />
            <MetricCard label="Palabras" value={fmt(m.total_words, 0)} />
            <MetricCard
              label="Velocidad media"
              value={fmt(m.avg_wpm)}
              unit="PPM"
              note="120–150 es referencia"
            />
            <MetricCard
              label="Muletillas"
              value={fmt(m.filler_count, 0)}
              unit={`(${fmt(m.filler_rate_per_min)}/min)`}
              note="Confianza 0.7"
            />
            <MetricCard
              label="Pausas ≥ 0.5s"
              value={fmt(m.pause_count, 0)}
              note={`avg ${fmt(m.avg_pause_duration)}s`}
            />
            <MetricCard
              label="Silencio"
              value={silencePct}
              unit="%"
              note="Del total de tiempo"
            />
            <MetricCard
              label="Variab. velocidad"
              value={fmt(m.wpm_std)}
              unit="σ PPM"
              note="Menor = más estable"
            />
            <MetricCard
              label="Variab. volumen"
              value={energyCvPct}
              unit="% CV"
              note="Mayor = más dinámico"
            />
          </div>
        </section>

        {/* Vision metrics — only shown if Phase 5 data is available */}
        {m.face_visible_ratio != null && (
          <section>
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
              Presencia visual — cámara y cuerpo
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              <MetricCard
                label="Cara visible"
                value={fmt((m.face_visible_ratio ?? 0) * 100, 0)}
                unit="% frames"
                note="Rostro detectado"
              />
              <MetricCard
                label="Mirando al frente"
                value={fmt((m.head_forward_ratio ?? 0) * 100, 0)}
                unit="% tiempo"
                note="|yaw|<20° y |pitch|<20°"
              />
              <MetricCard
                label="Rotación horizontal"
                value={fmt(m.head_yaw_mean)}
                unit={`° ± ${fmt(m.head_yaw_std)}`}
                note="+ = girado a la derecha"
              />
              <MetricCard
                label="Inclinación vertical"
                value={fmt(m.head_pitch_mean)}
                unit={`° ± ${fmt(m.head_pitch_std)}`}
                note="+ = inclinado hacia abajo"
              />
              <MetricCard
                label="Movimiento corporal"
                value={fmt((m.body_movement_mean ?? 0) * 100, 2)}
                unit="norm ×100"
                note="Hombros/cadera entre frames"
              />
            </div>
            <p className="text-xs text-gray-600 mt-3">
              Confianza 0.75–0.9 · Medido desde landmarks de MediaPipe, sin inferencia de intención
            </p>
          </section>
        )}

        {/* Rubric scores */}
        {rubric.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
              Dimensiones evaluadas — Rúbrica v1.0
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {rubric.map((r, i) => <RubricCard key={i} r={r} />)}
            </div>
            <p className="text-xs text-gray-600 mt-3">
              Scores calculados desde métricas medidas con fórmulas documentadas y transparentes.
              No representan juicio de valor — indican distancia respecto al rango de referencia.
            </p>
          </section>
        )}

        {/* Feedback */}
        {feedback.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-5">
              Retroalimentación basada en evidencia
            </h2>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="space-y-6">
                <FeedbackSection
                  items={feedback}
                  category="strength"
                  title="Fortalezas"
                  color="text-emerald-400"
                />
                <FeedbackSection
                  items={feedback}
                  category="exercise"
                  title="Ejercicios"
                  color="text-sky-400"
                />
              </div>
              <FeedbackSection
                items={feedback}
                category="improvement"
                title="Áreas de mejora"
                color="text-amber-400"
              />
            </div>
          </section>
        )}

        {/* Timeline Events */}
        {timeline.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
              Eventos en la línea de tiempo
            </h2>
            <div className="space-y-1.5">
              {timeline.map((evt, i) => (
                <TimelineRow key={i} evt={evt} />
              ))}
            </div>
          </section>
        )}

        {/* Transcript */}
        {transcript.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
              Transcripción
            </h2>
            <div className="bg-gray-900 rounded-xl p-5 max-h-96 overflow-y-auto space-y-3">
              {transcript.map((seg, i) => (
                <div key={i} className="flex gap-4 text-sm">
                  <span className="text-gray-600 font-mono w-16 flex-shrink-0 pt-0.5">
                    {Math.floor(seg.start_seconds / 60)}:{String(Math.floor(seg.start_seconds % 60)).padStart(2, '0')}
                  </span>
                  <p className="text-gray-300 leading-relaxed">{seg.text}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Evidence note */}
        <p className="text-xs text-gray-600 text-center pb-4">
          Todo el análisis está basado en datos medidos. Los valores etiquetados como &quot;inferidos&quot; están
          claramente marcados en el feedback. Modelo: claude-haiku-4-5-20251001.
        </p>
      </div>
    </div>
  )
}
