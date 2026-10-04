import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ComposedChart, AreaChart, LineChart,
  Area, Line, XAxis, YAxis, Tooltip, ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import { getReport, getChartData, videoUrl, Report, ChartData, TimelineEvent } from '../lib/api'

// ── Helpers ───────────────────────────────────────────────────────────────────

function tc(s: number): string {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

const LAYER_BG: Record<string, string> = {
  audio:  '#1e3a5f',
  speech: '#3b1f5e',
  vision: '#0f3d35',
}
const LAYER_BORDER: Record<string, string> = {
  audio:  '#3b82f6',
  speech: '#a855f7',
  vision: '#14b8a6',
}
const EVENT_ICONS: Record<string, string> = {
  pause:          '⏸',
  wpm_sprint:     '⚡',
  filler_cluster: '💬',
  head_away:      '↩️',
  face_absent:    '👻',
  movement_spike: '🌊',
}

// ── Custom tooltip ─────────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: number
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="text-gray-400 mb-1">{tc(label ?? 0)}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>{p.name}: {p.value?.toFixed(1)}</p>
      ))}
    </div>
  )
}

// ── EventTimeline ─────────────────────────────────────────────────────────────

function EventTimeline({
  events, duration, currentTime, onSeek,
}: {
  events: TimelineEvent[]
  duration: number
  currentTime: number
  onSeek: (t: number) => void
}) {
  const handleClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    onSeek(ratio * duration)
  }, [duration, onSeek])

  return (
    <div
      className="relative h-9 bg-gray-800 rounded-lg cursor-pointer select-none overflow-hidden"
      onClick={handleClick}
      title="Click para saltar a ese momento"
    >
      {/* Event blocks */}
      {events.map((evt, i) => {
        const left = (evt.start_seconds / duration) * 100
        const width = Math.max(0.4, (((evt.duration_seconds ?? 0.5) / duration) * 100))
        return (
          <div
            key={i}
            className="absolute top-1.5 bottom-1.5 rounded-sm cursor-pointer transition-opacity hover:opacity-100 opacity-75"
            style={{
              left: `${left}%`,
              width: `${width}%`,
              backgroundColor: LAYER_BORDER[evt.layer] ?? '#6b7280',
            }}
            onClick={(e) => { e.stopPropagation(); onSeek(evt.start_seconds) }}
            title={evt.description ?? evt.event_type}
          />
        )
      })}
      {/* Playhead */}
      <div
        className="absolute top-0 bottom-0 w-0.5 bg-white z-10 pointer-events-none"
        style={{ left: `${(currentTime / duration) * 100}%` }}
      />
    </div>
  )
}

// ── EventList ─────────────────────────────────────────────────────────────────

function EventList({
  events, currentTime, onSeek,
}: {
  events: TimelineEvent[]
  currentTime: number
  onSeek: (t: number) => void
}) {
  return (
    <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
      {events.map((evt, i) => {
        const active = currentTime >= evt.start_seconds &&
          currentTime <= (evt.end_seconds ?? evt.start_seconds + 1)
        return (
          <button
            key={i}
            onClick={() => onSeek(evt.start_seconds)}
            className={[
              'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-left transition-colors',
              active ? 'bg-gray-700' : 'bg-gray-900 hover:bg-gray-800',
            ].join(' ')}
          >
            <span className="font-mono text-gray-500 w-10 flex-shrink-0">{tc(evt.start_seconds)}</span>
            <span className="flex-shrink-0">{EVENT_ICONS[evt.event_type] ?? '•'}</span>
            <span className="text-gray-300 flex-1 truncate">{evt.description ?? evt.event_type}</span>
            <span
              className="text-xs px-1.5 py-0.5 rounded flex-shrink-0"
              style={{
                backgroundColor: LAYER_BG[evt.layer] ?? '#374151',
                color: LAYER_BORDER[evt.layer] ?? '#9ca3af',
              }}
            >
              {evt.layer}
            </span>
          </button>
        )
      })}
      {events.length === 0 && (
        <p className="text-gray-600 text-sm text-center py-4">Sin eventos detectados</p>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { id } = useParams<{ id: string }>()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [chartData, setChartData] = useState<ChartData | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    const pid = Number(id)
    Promise.all([getReport(pid), getChartData(pid)])
      .then(([r, c]) => { setReport(r); setChartData(c) })
      .catch(e => setError((e as Error).message))
  }, [id])

  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) setCurrentTime(videoRef.current.currentTime)
  }, [])

  const seek = useCallback((t: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = t
      videoRef.current.play().catch(() => {})
    }
  }, [])

  if (error) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-red-400">{error}</p>
          <Link to="/" className="text-indigo-400 text-sm hover:underline">← Inicio</Link>
        </div>
      </div>
    )
  }

  if (!report || !chartData) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <p className="text-gray-400 animate-pulse">Cargando dashboard…</p>
      </div>
    )
  }

  const duration = report.duration_seconds ?? chartData.duration_seconds ?? 1
  const audio = chartData.audio
  const videoFrames = chartData.video
  const hasVision = videoFrames.some(f => f.yaw !== null)

  // X axis formatter
  const xFmt = (v: number) => tc(v)

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <div className="border-b border-gray-800 px-6 py-3 flex items-center gap-4">
        <Link to={`/report/${report.id}`} className="text-indigo-400 text-sm hover:underline flex-shrink-0">
          ← Reporte
        </Link>
        <h1 className="font-semibold text-white truncate flex-1">{report.title}</h1>
        <span className="text-gray-500 text-sm flex-shrink-0">{tc(currentTime)} / {tc(duration)}</span>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">

        {/* Video + event timeline */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Video player */}
          <div className="lg:col-span-2 space-y-3">
            <video
              ref={videoRef}
              src={videoUrl(report.id)}
              controls
              onTimeUpdate={handleTimeUpdate}
              className="w-full rounded-xl bg-black aspect-video"
            />
            {/* Event timeline bar */}
            <EventTimeline
              events={report.timeline}
              duration={duration}
              currentTime={currentTime}
              onSeek={seek}
            />
            <div className="flex gap-4 text-xs text-gray-600">
              {(['audio', 'speech', 'vision'] as const).map(layer => (
                <span key={layer} className="flex items-center gap-1">
                  <span
                    className="inline-block w-3 h-3 rounded-sm"
                    style={{ backgroundColor: LAYER_BORDER[layer] }}
                  />
                  {layer}
                </span>
              ))}
              <span className="ml-2">Click en la barra para saltar</span>
            </div>
          </div>

          {/* Events list */}
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Eventos ({report.timeline.length})
            </h2>
            <EventList events={report.timeline} currentTime={currentTime} onSeek={seek} />
          </div>
        </div>

        {/* WPM chart */}
        {audio.length > 0 && (
          <div className="bg-gray-900 rounded-xl p-4">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Velocidad del habla (PPM)
            </h2>
            <ResponsiveContainer width="100%" height={160}>
              <ComposedChart data={audio} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <XAxis dataKey="t" tickFormatter={xFmt} tick={{ fill: '#6b7280', fontSize: 10 }} minTickGap={60} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} width={36} domain={[0, 'auto']} />
                <Tooltip content={<ChartTooltip />} />
                <Area
                  type="monotone" dataKey="wpm" name="PPM"
                  stroke="#6366f1" fill="#6366f122" strokeWidth={1.5} dot={false}
                />
                <ReferenceLine x={currentTime} stroke="#ffffff44" strokeWidth={1} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Energy/volume chart */}
        {audio.length > 0 && (
          <div className="bg-gray-900 rounded-xl p-4">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Volumen (RMS)
            </h2>
            <ResponsiveContainer width="100%" height={130}>
              <AreaChart data={audio} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <XAxis dataKey="t" tickFormatter={xFmt} tick={{ fill: '#6b7280', fontSize: 10 }} minTickGap={60} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} width={36} />
                <Tooltip content={<ChartTooltip />} />
                <Area
                  type="monotone" dataKey="rms" name="RMS"
                  stroke="#10b981" fill="#10b98122" strokeWidth={1.5} dot={false}
                />
                <ReferenceLine x={currentTime} stroke="#ffffff44" strokeWidth={1} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Head yaw chart — only when vision data available */}
        {hasVision && (
          <div className="bg-gray-900 rounded-xl p-4">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
              Orientación de cabeza — yaw (°)
            </h2>
            <p className="text-xs text-gray-600 mb-3">
              + = girado a la derecha · – = girado a la izquierda · banda gris = ±35° (umbral "girado")
            </p>
            <ResponsiveContainer width="100%" height={130}>
              <LineChart data={videoFrames} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <XAxis dataKey="t" tickFormatter={xFmt} tick={{ fill: '#6b7280', fontSize: 10 }} minTickGap={60} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} width={36} domain={[-90, 90]} />
                <Tooltip content={<ChartTooltip />} />
                <ReferenceLine y={35} stroke="#f59e0b44" strokeDasharray="4 2" />
                <ReferenceLine y={-35} stroke="#f59e0b44" strokeDasharray="4 2" />
                <ReferenceLine y={0} stroke="#ffffff22" />
                <ReferenceLine x={currentTime} stroke="#ffffff44" strokeWidth={1} />
                <Line
                  type="monotone" dataKey="yaw" name="Yaw"
                  stroke="#14b8a6" dot={false} strokeWidth={1.5}
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

      </div>
    </div>
  )
}
