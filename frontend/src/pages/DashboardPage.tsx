import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import {
  ComposedChart, AreaChart, LineChart,
  Area, Line, XAxis, YAxis, Tooltip, ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import { getReport, getChartData, videoUrl, Report, ChartData, TimelineEvent } from '../lib/api'
import IFLogo from '../components/IFLogo'
import FaceMeshOverlay from '../components/FaceMeshOverlay'

function tc(s: number): string {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

const LAYER_COLOR: Record<string, string> = {
  audio:  '#1A5FFF',
  speech: '#7C3AED',
  vision: '#059669',
}

const EVT_LABEL: Record<string, string> = {
  pause:          'Pausa',
  wpm_sprint:     'Aceleración',
  filler_cluster: 'Cluster muletillas',
  head_away:      'Cabeza girada',
  face_absent:    'Sin cara',
  movement_spike: 'Movimiento',
}

const AGGREGATE_EVENTS = new Set([
  'pause', 'wpm_sprint', 'filler_cluster', 'head_away', 'face_absent', 'movement_spike',
])

function ChartTooltip({ active, payload, label }: {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: number
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-[#E4E4EE] rounded-lg px-3 py-2 text-xs shadow-md">
      <p className="text-[#9090A8] mb-1 font-mono">{tc(label ?? 0)}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>{p.name}: {p.value?.toFixed(1)}</p>
      ))}
    </div>
  )
}

function EventTimeline({ events, duration, currentTime, onSeek }: {
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
      className="relative h-6 bg-[#F0F0F8] border border-[#DCDCEC] rounded cursor-pointer select-none overflow-hidden"
      onClick={handleClick}
      title="Click para saltar"
    >
      {events.map((evt, i) => {
        const left  = (evt.start_seconds / duration) * 100
        const width = Math.max(0.5, ((evt.duration_seconds ?? 0.5) / duration) * 100)
        return (
          <div
            key={i}
            className="absolute top-1 bottom-1 rounded-sm opacity-80 hover:opacity-100 cursor-pointer transition-opacity"
            style={{ left: `${left}%`, width: `${width}%`, backgroundColor: LAYER_COLOR[evt.layer] ?? '#9090A8' }}
            onClick={(e) => { e.stopPropagation(); onSeek(evt.start_seconds) }}
            title={evt.description ?? evt.event_type}
          />
        )
      })}
      <div
        className="absolute top-0 bottom-0 w-px bg-[#0C0C18] z-10 pointer-events-none"
        style={{ left: `${(currentTime / duration) * 100}%` }}
      />
    </div>
  )
}

function EventList({ events, currentTime, onSeek }: {
  events: TimelineEvent[]
  currentTime: number
  onSeek: (t: number) => void
}) {
  return (
    <div className="space-y-px max-h-64 overflow-y-auto">
      {events.map((evt, i) => {
        const active = currentTime >= evt.start_seconds &&
          currentTime <= (evt.end_seconds ?? evt.start_seconds + 1)
        return (
          <button
            key={i}
            onClick={() => onSeek(evt.start_seconds)}
            className={[
              'w-full flex items-center gap-3 px-3 py-2 rounded text-left transition-colors',
              active ? 'bg-[#EEF3FF]' : 'hover:bg-[#F4F4F8]',
            ].join(' ')}
          >
            <span className={`font-mono text-xs w-10 flex-shrink-0 ${active ? 'text-[#1A5FFF] font-semibold' : 'text-[#9090A8]'}`}>
              {tc(evt.start_seconds)}
            </span>
            <span className="text-xs text-[#2C2C3E] flex-1 truncate text-left">
              {evt.description ?? EVT_LABEL[evt.event_type] ?? evt.event_type}
            </span>
            <span
              className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0 font-medium"
              style={{ color: LAYER_COLOR[evt.layer] ?? '#9090A8', backgroundColor: `${LAYER_COLOR[evt.layer] ?? '#9090A8'}18` }}
            >
              {evt.layer}
            </span>
          </button>
        )
      })}
      {events.length === 0 && (
        <p className="text-[#ABABC8] text-xs text-center py-6">Sin eventos detectados</p>
      )}
    </div>
  )
}

export default function DashboardPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [report, setReport]     = useState<Report | null>(null)
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

  useEffect(() => {
    const t = parseFloat(searchParams.get('t') ?? '')
    if (!isNaN(t) && videoRef.current) {
      videoRef.current.currentTime = t
    }
  }, [searchParams, report])

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
      <div className="min-h-screen bg-[#F4F4F8] flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-[#EF4444] text-sm">{error}</p>
          <Link to="/" className="text-xs text-[#9090A8] hover:underline">← Inicio</Link>
        </div>
      </div>
    )
  }

  if (!report || !chartData) {
    return (
      <div className="min-h-screen bg-[#F4F4F8] flex items-center justify-center">
        <div className="w-24 h-0.5 bg-[#1A5FFF] animate-pulse rounded-full" />
      </div>
    )
  }

  const duration       = report.duration_seconds ?? chartData.duration_seconds ?? 1
  const audio          = chartData.audio
  const videoFrames    = chartData.video
  const hasVision      = videoFrames.some(f => f.yaw !== null)
  const aggEvents      = report.timeline.filter(e => AGGREGATE_EVENTS.has(e.event_type))
  const xFmt           = (v: number) => tc(v)

  const axisProps = { fill: '#9090A8', fontSize: 10 }

  return (
    <div className="min-h-screen bg-[#F4F4F8] text-[#0C0C18]">
      {/* Header */}
      <header className="bg-white border-b border-[#E4E4EE] px-6 py-4 flex items-center gap-4">
        <IFLogo size="sm" />
        <Link to={`/report/${report.id}`} className="text-xs text-[#9090A8] hover:text-[#0C0C18] transition-colors ml-2 flex-shrink-0">
          ← Reporte
        </Link>
        <h1 className="text-sm font-medium text-[#2C2C3E] truncate flex-1">{report.title}</h1>
        <Link to="/history" className="text-xs text-[#9090A8] hover:text-[#0C0C18] transition-colors flex-shrink-0">Historial</Link>
        <span className="text-xs font-mono text-[#9090A8] flex-shrink-0">{tc(currentTime)} / {tc(duration)}</span>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-6 space-y-5">

        {/* Video + events */}
        <div className="grid lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 space-y-2">
            <div className="relative">
              <video
                ref={videoRef}
                src={videoUrl(report.id)}
                controls
                onTimeUpdate={handleTimeUpdate}
                className="w-full rounded-lg bg-black aspect-video shadow-sm"
              />
              <FaceMeshOverlay videoRef={videoRef} />
            </div>
            <EventTimeline events={aggEvents} duration={duration} currentTime={currentTime} onSeek={seek} />
            <div className="flex gap-5 text-[10px] text-[#ABABC8]">
              {(['audio', 'speech', 'vision'] as const).map(layer => (
                <span key={layer} className="flex items-center gap-1.5">
                  <span className="inline-block w-2 h-2 rounded-sm" style={{ backgroundColor: LAYER_COLOR[layer] }} />
                  {layer}
                </span>
              ))}
              <span className="ml-1">Click en la barra para saltar</span>
            </div>
          </div>

          <div className="bg-white border border-[#E4E4EE] rounded-lg p-4">
            <p className="text-[11px] font-semibold tracking-[0.14em] uppercase text-[#9090A8] mb-3">
              Eventos ({aggEvents.length})
            </p>
            <EventList events={aggEvents} currentTime={currentTime} onSeek={seek} />
          </div>
        </div>

        {/* WPM chart */}
        {audio.length > 0 && (
          <div className="bg-white border border-[#E4E4EE] rounded-lg p-4">
            <p className="text-[11px] font-semibold tracking-[0.14em] uppercase text-[#9090A8] mb-4">
              Velocidad del habla (PPM)
            </p>
            <ResponsiveContainer width="100%" height={150}>
              <ComposedChart data={audio} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <XAxis dataKey="t" tickFormatter={xFmt} tick={axisProps} minTickGap={60} />
                <YAxis tick={axisProps} width={36} domain={[0, 'auto']} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="wpm" name="PPM" stroke="#1A5FFF" fill="#1A5FFF18" strokeWidth={1.5} dot={false} />
                <ReferenceLine x={currentTime} stroke="#0C0C1866" strokeWidth={1} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Volume chart */}
        {audio.length > 0 && (
          <div className="bg-white border border-[#E4E4EE] rounded-lg p-4">
            <p className="text-[11px] font-semibold tracking-[0.14em] uppercase text-[#9090A8] mb-4">
              Volumen (RMS)
            </p>
            <ResponsiveContainer width="100%" height={120}>
              <AreaChart data={audio} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <XAxis dataKey="t" tickFormatter={xFmt} tick={axisProps} minTickGap={60} />
                <YAxis tick={axisProps} width={36} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="rms" name="RMS" stroke="#059669" fill="#05966918" strokeWidth={1.5} dot={false} />
                <ReferenceLine x={currentTime} stroke="#0C0C1866" strokeWidth={1} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Yaw chart */}
        {hasVision && (
          <div className="bg-white border border-[#E4E4EE] rounded-lg p-4">
            <p className="text-[11px] font-semibold tracking-[0.14em] uppercase text-[#9090A8] mb-1">
              Orientación de cabeza — yaw (°)
            </p>
            <p className="text-[10px] text-[#ABABC8] mb-4">
              + = girado a la derecha · – = izquierda · líneas amarillas = ±35° (umbral)
            </p>
            <ResponsiveContainer width="100%" height={120}>
              <LineChart data={videoFrames} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <XAxis dataKey="t" tickFormatter={xFmt} tick={axisProps} minTickGap={60} />
                <YAxis tick={axisProps} width={36} domain={[-90, 90]} />
                <Tooltip content={<ChartTooltip />} />
                <ReferenceLine y={35}  stroke="#D9770666" strokeDasharray="4 2" />
                <ReferenceLine y={-35} stroke="#D9770666" strokeDasharray="4 2" />
                <ReferenceLine y={0}   stroke="#DCDCEC" />
                <ReferenceLine x={currentTime} stroke="#0C0C1866" strokeWidth={1} />
                <Line type="monotone" dataKey="yaw" name="Yaw" stroke="#7C3AED" dot={false} strokeWidth={1.5} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
