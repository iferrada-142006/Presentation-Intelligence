import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getReport, Report } from '../lib/api'

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

  const { metrics: m, transcript, feedback } = report
  const durationMin = report.duration_seconds ? (report.duration_seconds / 60).toFixed(1) : '—'
  const silencePct = m.silence_ratio != null ? (m.silence_ratio * 100).toFixed(1) : '—'
  const energyCvPct = m.energy_cv != null ? (m.energy_cv * 100).toFixed(1) : '—'

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 py-10 px-4">
      <div className="max-w-4xl mx-auto space-y-10">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <Link to="/" className="text-indigo-400 text-sm hover:underline mb-2 inline-block">
              ← Nueva presentación
            </Link>
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
            Métricas observadas
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
