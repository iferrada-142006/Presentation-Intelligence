import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listPresentations, PresentationListItem } from '../lib/api'
import IFLogo from '../components/IFLogo'

function tc(s: number): string {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

function ScoreRing({ score }: { score: number }) {
  const r = 20
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  const color = score >= 75 ? '#10B981' : score >= 50 ? '#1A5FFF' : score >= 30 ? '#F97316' : '#EF4444'

  return (
    <svg width={52} height={52} className="flex-shrink-0">
      <circle cx={26} cy={26} r={r} fill="none" stroke="#EBEBF4" strokeWidth={4} />
      <circle
        cx={26} cy={26} r={r}
        fill="none"
        stroke={color}
        strokeWidth={4}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        transform="rotate(-90 26 26)"
        style={{ transition: 'stroke-dashoffset 0.8s cubic-bezier(0.16,1,0.3,1)' }}
      />
      <text x={26} y={30} textAnchor="middle" fontSize={11} fontWeight={700} fill={color}>
        {Math.round(score)}
      </text>
    </svg>
  )
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  complete:   { label: 'Completo',    cls: 'bg-[#D1FAE5] text-[#059669]' },
  processing: { label: 'Procesando',  cls: 'bg-[#DBEAFE] text-[#2563EB]' },
  queued:     { label: 'En cola',     cls: 'bg-[#F3F4F6] text-[#6B7280]' },
  failed:     { label: 'Error',       cls: 'bg-[#FEE2E2] text-[#DC2626]' },
}

function PresentationCard({ item, index }: { item: PresentationListItem; index: number }) {
  const badge  = STATUS_BADGE[item.status] ?? STATUS_BADGE.queued
  const date   = new Date(item.uploaded_at).toLocaleDateString('es-CL', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
  const isComplete = item.status === 'complete'

  return (
    <div
      className="animate-fade-up bg-white border border-[#EBEBF4] rounded-2xl p-5 hover:shadow-md hover:border-[#DCDCEC] transition-all flex items-center gap-5"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {/* Score ring or placeholder */}
      {item.avg_score != null ? (
        <ScoreRing score={item.avg_score} />
      ) : (
        <div className="w-[52px] h-[52px] rounded-full border-4 border-[#EBEBF4] flex items-center justify-center flex-shrink-0">
          <span className="text-[#DCDCEC] text-lg">—</span>
        </div>
      )}

      {/* Main info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <h2 className="text-sm font-semibold text-[#0C0C18] truncate">{item.title}</h2>
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold flex-shrink-0 ${badge.cls}`}>
            {badge.label}
          </span>
        </div>
        <p className="text-xs text-[#9090A8]">
          {date}
          {item.duration_seconds != null && <> · {tc(item.duration_seconds)}</>}
          {item.language && <> · {item.language === 'es' ? 'Español' : 'English'}</>}
        </p>
        {isComplete && (item.avg_wpm != null || item.filler_count != null) && (
          <div className="flex items-center gap-4 mt-2">
            {item.avg_wpm != null && (
              <span className="text-xs text-[#6060A0]">
                <span className="font-semibold text-[#0C0C18]">{Math.round(item.avg_wpm)}</span> PPM
              </span>
            )}
            {item.filler_count != null && (
              <span className="text-xs text-[#6060A0]">
                <span className="font-semibold text-[#0C0C18]">{Math.round(item.filler_count)}</span> muletillas
              </span>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {isComplete ? (
          <>
            <Link
              to={`/report/${item.id}`}
              className="text-xs font-medium px-3 py-1.5 rounded-lg bg-[#1A5FFF] text-white hover:bg-[#1550E0] transition-colors"
            >
              Reporte
            </Link>
            <Link
              to={`/dashboard/${item.id}`}
              className="text-xs font-medium px-3 py-1.5 rounded-lg border border-[#DCDCEC] text-[#6060A0] hover:border-[#1A5FFF] hover:text-[#1A5FFF] transition-colors"
            >
              Dashboard
            </Link>
          </>
        ) : (
          <span className="text-xs text-[#ABABC8]">
            {item.status === 'processing' ? 'Analizando…' : 'Pendiente'}
          </span>
        )}
      </div>
    </div>
  )
}

export default function HistoryPage() {
  const [items, setItems]   = useState<PresentationListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')

  useEffect(() => {
    listPresentations()
      .then(setItems)
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [])

  const complete   = items.filter(i => i.status === 'complete')
  const inProgress = items.filter(i => i.status !== 'complete')
  const avgScore   = complete.length && complete.some(i => i.avg_score != null)
    ? complete.filter(i => i.avg_score != null).reduce((s, i) => s + i.avg_score!, 0) /
      complete.filter(i => i.avg_score != null).length
    : null

  return (
    <div className="min-h-screen bg-[#F4F4F8]">
      {/* Header */}
      <header className="bg-white border-b border-[#E4E4EE] px-6 py-4 flex items-center gap-4 sticky top-0 z-30 shadow-sm">
        <IFLogo size="sm" />
        <h1 className="text-sm font-semibold text-[#0C0C18] ml-2 flex-1">Historial</h1>
        <Link to="/" className="text-xs font-medium px-3 py-1.5 rounded-lg bg-[#1A5FFF] text-white hover:bg-[#1550E0] transition-colors">
          + Nueva presentación
        </Link>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-8">

        {/* Summary bar */}
        {!loading && complete.length > 0 && (
          <div className="animate-fade-in grid grid-cols-3 gap-4 mb-8 p-5 bg-white rounded-2xl border border-[#EBEBF4] shadow-sm">
            <div className="text-center">
              <p className="text-3xl font-bold text-[#0C0C18]">{complete.length}</p>
              <p className="text-xs text-[#9090A8] mt-1">Analizadas</p>
            </div>
            <div className="text-center border-x border-[#EBEBF4]">
              <p className="text-3xl font-bold text-[#1A5FFF]">
                {avgScore != null ? Math.round(avgScore) : '—'}
              </p>
              <p className="text-xs text-[#9090A8] mt-1">Score promedio</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-[#0C0C18]">
                {complete.filter(i => i.avg_wpm != null).length > 0
                  ? Math.round(complete.filter(i => i.avg_wpm != null)
                      .reduce((s, i) => s + i.avg_wpm!, 0) /
                      complete.filter(i => i.avg_wpm != null).length)
                  : '—'}
              </p>
              <p className="text-xs text-[#9090A8] mt-1">PPM promedio</p>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="w-32 h-0.5 bg-[#1A5FFF] animate-pulse rounded-full" />
          </div>
        )}

        {error && (
          <p className="text-[#EF4444] text-sm text-center py-10">{error}</p>
        )}

        {!loading && items.length === 0 && (
          <div className="text-center py-20 space-y-3">
            <p className="text-[#9090A8] text-sm">No hay presentaciones todavía.</p>
            <Link to="/" className="text-xs text-[#1A5FFF] hover:underline underline-offset-4">
              Sube tu primera presentación →
            </Link>
          </div>
        )}

        {inProgress.length > 0 && (
          <div className="mb-6 space-y-2">
            <p className="text-[11px] font-bold tracking-[0.18em] uppercase text-[#9090A8] mb-4">En proceso</p>
            {inProgress.map((item, i) => <PresentationCard key={item.id} item={item} index={i} />)}
          </div>
        )}

        {complete.length > 0 && (
          <div className="space-y-2">
            {inProgress.length > 0 && (
              <p className="text-[11px] font-bold tracking-[0.18em] uppercase text-[#9090A8] mb-4">Completadas</p>
            )}
            {complete.map((item, i) => <PresentationCard key={item.id} item={item} index={i} />)}
          </div>
        )}
      </div>
    </div>
  )
}
