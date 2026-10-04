import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getReport, Report, RubricScore, TimelineEvent } from '../lib/api'
import IFLogo from '../components/IFLogo'
import { useCountUp } from '../hooks/useCountUp'
import { useActiveSection } from '../hooks/useActiveSection'

function tc(s: number): string {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

// ── Info tooltip ──────────────────────────────────────────────────────────────

function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline-flex items-center ml-1.5 align-middle">
      <button
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onClick={() => setOpen(o => !o)}
        className="w-4 h-4 rounded-full bg-[#EBEBF4] text-[#9090A8] text-[10px] font-bold inline-flex items-center justify-center hover:bg-[#DCDCEC] hover:text-[#0C0C18] transition-colors flex-shrink-0"
        aria-label="Más información"
        type="button"
      >?</button>
      {open && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2.5 w-64 bg-[#0C0C18] text-white text-[11px] rounded-xl px-3.5 py-3 leading-relaxed shadow-2xl z-50 pointer-events-none">
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-[#0C0C18]" />
        </span>
      )}
    </span>
  )
}

// ── Animated big stat ─────────────────────────────────────────────────────────

function BigStat({ label, value, unit, sub, delay = 0, help }: {
  label: string; value: number; unit?: string; sub?: string; delay?: number; help?: string
}) {
  const d = unit === '%' ? 1 : value < 10 ? 1 : 0
  const display = useCountUp(value, 900, d)
  return (
    <div
      className="animate-fade-up"
      style={{ animationDelay: `${delay}ms` }}
    >
      <p className="text-xs text-[#9090A8] font-medium mb-1 flex items-center">
        {label}
        {help && <InfoTip text={help} />}
      </p>
      <p className="text-5xl font-bold text-[#0C0C18] leading-none tabular-nums">
        {display}
        {unit && <span className="text-xl font-medium text-[#9090A8] ml-1">{unit}</span>}
      </p>
      {sub && <p className="text-xs text-[#ABABC8] mt-2">{sub}</p>}
    </div>
  )
}

function SmallStat({ label, value, unit, sub, help }: {
  label: string; value: string; unit?: string; sub?: string; help?: string
}) {
  return (
    <div className="py-3 border-b border-[#EBEBF4] last:border-0">
      <p className="text-[11px] text-[#9090A8] mb-0.5 flex items-center">
        {label}
        {help && <InfoTip text={help} />}
      </p>
      <p className="text-xl font-semibold text-[#0C0C18]">
        {value}
        {unit && <span className="text-sm font-normal text-[#9090A8] ml-1">{unit}</span>}
      </p>
      {sub && <p className="text-xs text-[#CCCCDE] mt-0.5">{sub}</p>}
    </div>
  )
}

// ── Rubric ────────────────────────────────────────────────────────────────────

const DIM_LABELS: Record<string, string> = {
  verbal_rhythm:      'Ritmo verbal',
  filler_density:     'Muletillas',
  silence_management: 'Gestión del silencio',
  vocal_dynamics:     'Dinámica vocal',
  visual_presence:    'Presencia visual',
}
const LEVEL_ACCENT: Record<number, string> = {
  0: '#EF4444', 1: '#F97316', 2: '#EAB308', 3: '#3B82F6', 4: '#10B981',
}

function RubricRow({ r, delay = 0 }: { r: RubricScore; delay?: number }) {
  const [visible, setVisible] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect() } }, { threshold: 0.3 })
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [])

  const accent = LEVEL_ACCENT[r.level] ?? '#1A5FFF'
  const label  = DIM_LABELS[r.dimension] ?? r.dimension

  return (
    <div ref={ref} className="py-4 border-b border-[#EBEBF4] animate-fade-up" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-[#2C2C3E]">{label}</span>
        <div className="flex items-center gap-3">
          <span className="text-xs px-2 py-0.5 rounded-full font-medium"
            style={{ backgroundColor: `${accent}18`, color: accent }}>
            {r.level_label}
          </span>
          <span className="text-2xl font-bold tabular-nums" style={{ color: accent }}>
            {r.score.toFixed(0)}
          </span>
        </div>
      </div>
      <div className="h-2 bg-[#EBEBF4] rounded-full overflow-hidden">
        <div
          className={`h-2 rounded-full transition-none ${visible ? 'animate-bar' : ''}`}
          style={{ width: visible ? `${r.score}%` : '0%', backgroundColor: accent }}
        />
      </div>
      {r.evidence && <p className="text-xs text-[#ABABC8] mt-2 leading-relaxed">{r.evidence}</p>}
    </div>
  )
}

// ── Filler chips ──────────────────────────────────────────────────────────────

function FillerChips({ pid, fillers, corrections }: {
  pid: number; fillers: TimelineEvent[]; corrections: TimelineEvent[]
}) {
  const byWord: Record<string, TimelineEvent[]> = {}
  for (const e of fillers) { const w = e.description ?? ''; (byWord[w] ??= []).push(e) }
  const sorted = Object.entries(byWord).sort((a, b) => b[1].length - a[1].length)
  if (!fillers.length && !corrections.length) return null

  return (
    <div className="mt-5 bg-[#F8F8FC] border border-[#EBEBF4] rounded-xl p-5 space-y-4">
      <p className="text-[11px] font-semibold tracking-[0.12em] uppercase text-[#9090A8]">
        Detalle — clic para ver en video
      </p>
      {sorted.map(([word, evts]) => (
        <div key={word} className="flex items-start gap-3 flex-wrap">
          <span className="text-sm font-mono font-semibold text-[#2C2C3E] w-28 flex-shrink-0">{word}</span>
          <span className="text-xs text-[#ABABC8] w-5 mt-0.5">×{evts.length}</span>
          <div className="flex flex-wrap gap-1.5">
            {evts.map((e, i) => (
              <Link key={i}
                to={`/dashboard/${pid}?t=${Math.max(0, e.start_seconds - 1).toFixed(1)}`}
                className="text-xs font-mono px-2.5 py-1 rounded-lg bg-white border border-[#DCDCEC] text-[#1A5FFF] hover:bg-[#EEF3FF] hover:border-[#1A5FFF] transition-all shadow-sm"
              >
                {tc(e.start_seconds)}
              </Link>
            ))}
          </div>
        </div>
      ))}
      {corrections.length > 0 && (
        <div className="pt-3 border-t border-[#EBEBF4]">
          <p className="text-[11px] text-[#9090A8] mb-2">Auto-correcciones</p>
          <div className="flex flex-wrap gap-2">
            {corrections.map((e, i) => (
              <Link key={i}
                to={`/dashboard/${pid}?t=${Math.max(0, e.start_seconds - 1).toFixed(1)}`}
                className="text-xs font-mono px-2.5 py-1 rounded-lg bg-[#FFFBEB] border border-[#FDE68A] text-[#D97706] hover:bg-[#FEF3C7] transition-all"
              >
                {tc(e.start_seconds)} {e.description}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Feedback ──────────────────────────────────────────────────────────────────

function FeedbackBlock({ items, pid }: { items: Report['feedback']; pid: number }) {
  const strengths    = items.filter(i => i.category === 'strength')
  const improvements = items.filter(i => i.category === 'improvement')
  const exercises    = items.filter(i => i.category === 'exercise')
  if (!items.length) return (
    <div className="text-center py-10 text-[#ABABC8] text-sm">
      Agrega una API key de Anthropic para generar retroalimentación
    </div>
  )

  return (
    <div className="space-y-10">
      {strengths.length > 0 && (
        <div className="space-y-3">
          <p className="text-[11px] font-semibold tracking-[0.16em] uppercase text-[#10B981]">Fortalezas</p>
          {strengths.map((s, i) => (
            <div key={i} className="animate-fade-up bg-white border border-[#EBEBF4] rounded-xl p-4 hover:shadow-md transition-shadow"
              style={{ animationDelay: `${i * 80}ms` }}>
              <p className="text-sm text-[#2C2C3E] leading-relaxed">{s.content}</p>
              {s.evidence && (
                <p className="text-xs text-[#9090A8] mt-2 pt-2 border-t border-[#F0F0F8]">{s.evidence}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {improvements.length > 0 && (
        <div className="space-y-4">
          <p className="text-[11px] font-semibold tracking-[0.16em] uppercase text-[#D97706]">Áreas de mejora</p>
          {improvements.map((imp, i) => (
            <div key={i} className="animate-fade-up" style={{ animationDelay: `${i * 80}ms` }}>
              <div className="bg-white border border-[#EBEBF4] rounded-xl p-4 hover:shadow-md transition-shadow">
                <p className="text-sm text-[#2C2C3E] leading-relaxed">{imp.content}</p>
                {imp.evidence && (
                  <p className="text-xs text-[#9090A8] mt-2 pt-2 border-t border-[#F0F0F8]">{imp.evidence}</p>
                )}
              </div>
              {exercises[i] && (
                <div className="mt-2 ml-4 bg-[#EEF3FF] border border-[#DDEAFF] rounded-xl p-4">
                  <p className="text-[10px] font-bold tracking-[0.14em] uppercase text-[#1A5FFF] mb-1.5">Ejercicio</p>
                  <p className="text-xs text-[#4466AA] leading-relaxed">{exercises[i].content}</p>
                  <Link to={`/dashboard/${pid}`}
                    className="text-[11px] text-[#1A5FFF] hover:underline mt-2 inline-flex items-center gap-1 font-medium">
                    Ver en video <span>→</span>
                  </Link>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Timeline ──────────────────────────────────────────────────────────────────

const EVT_LABEL: Record<string, string> = {
  pause: 'Pausa detectada', wpm_sprint: 'Aceleración del habla',
  filler_cluster: 'Cluster de muletillas', head_away: 'Cabeza girada',
  face_absent: 'Sin rostro', movement_spike: 'Movimiento corporal',
}
const EVT_COLOR: Record<string, string> = {
  pause: '#9090A8', wpm_sprint: '#1A5FFF', filler_cluster: '#7C3AED',
  head_away: '#D97706', face_absent: '#EF4444', movement_spike: '#059669',
}

function EventCard({ evt, pid, i }: { evt: TimelineEvent; pid: number; i: number }) {
  const accent = EVT_COLOR[evt.event_type] ?? '#9090A8'
  return (
    <Link
      to={`/dashboard/${pid}?t=${Math.max(0, evt.start_seconds - 1).toFixed(1)}`}
      className="animate-fade-up flex items-start gap-4 bg-white border border-[#EBEBF4] rounded-xl p-4 hover:shadow-md hover:border-[#DCDCEC] transition-all group"
      style={{ animationDelay: `${i * 60}ms` }}
    >
      <div className="w-1 self-stretch rounded-full flex-shrink-0" style={{ backgroundColor: accent }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-mono text-xs font-semibold" style={{ color: accent }}>{tc(evt.start_seconds)}</span>
          <span className="text-[10px] text-[#ABABC8] px-1.5 py-0.5 bg-[#F4F4F8] rounded">{evt.layer}</span>
        </div>
        <p className="text-sm text-[#2C2C3E] leading-relaxed">{evt.description ?? EVT_LABEL[evt.event_type] ?? evt.event_type}</p>
      </div>
      <span className="text-xs text-[#1A5FFF] opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 self-center">
        Ver →
      </span>
    </Link>
  )
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

const SECTIONS = [
  { id: 'voz',       label: 'Voz y audio' },
  { id: 'visual',    label: 'Presencia visual' },
  { id: 'rubrica',   label: 'Rúbrica' },
  { id: 'feedback',  label: 'Retroalimentación' },
  { id: 'eventos',   label: 'Eventos' },
  { id: 'transcript',label: 'Transcripción' },
]

function Sidebar({ active, onSelect, hasVision, hasFeedback, hasTimeline, hasTranscript }: {
  active: string; onSelect: (id: string) => void
  hasVision: boolean; hasFeedback: boolean; hasTimeline: boolean; hasTranscript: boolean
}) {
  const visible = SECTIONS.filter(s =>
    (s.id !== 'visual'     || hasVision) &&
    (s.id !== 'feedback'   || hasFeedback) &&
    (s.id !== 'eventos'    || hasTimeline) &&
    (s.id !== 'transcript' || hasTranscript)
  )

  return (
    <aside className="w-64 flex-shrink-0 sticky top-[72px] self-start hidden lg:block animate-fade-in">
      <nav className="space-y-1">
        {visible.map(s => (
          <a
            key={s.id}
            href={`#${s.id}`}
            onClick={() => onSelect(s.id)}
            className={[
              'flex items-center gap-3 px-4 py-3 rounded-xl text-base font-medium transition-all',
              active === s.id
                ? 'bg-white shadow text-[#0C0C18] font-semibold border border-[#EBEBF4]'
                : 'text-[#9090A8] hover:text-[#0C0C18] hover:bg-white/70',
            ].join(' ')}
          >
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 transition-colors ${active === s.id ? 'bg-[#1A5FFF]' : 'bg-[#DCDCEC]'}`}
            />
            {s.label}
          </a>
        ))}
      </nav>
    </aside>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError]   = useState('')

  useEffect(() => {
    if (!id) return
    getReport(Number(id)).then(setReport).catch(e => setError((e as Error).message))
  }, [id])

  const sectionIds = SECTIONS.map(s => s.id)
  const [activeSection, setActiveSection] = useActiveSection(sectionIds)

  if (error) return (
    <div className="min-h-screen bg-[#F4F4F8] flex items-center justify-center">
      <div className="text-center space-y-3">
        <p className="text-[#EF4444] text-sm">{error}</p>
        <Link to="/" className="text-xs text-[#9090A8] hover:underline underline-offset-4">← Volver</Link>
      </div>
    </div>
  )

  if (!report) return (
    <div className="min-h-screen bg-[#F4F4F8] flex items-center justify-center">
      <div className="space-y-3 text-center">
        <div className="w-32 h-0.5 bg-[#1A5FFF] animate-pulse rounded-full mx-auto" />
        <p className="text-xs text-[#9090A8]">Cargando análisis…</p>
      </div>
    </div>
  )

  const { metrics: m, rubric, transcript, timeline, feedback } = report
  const dur        = report.duration_seconds ?? 0
  const silencePct = (m.silence_ratio ?? 0) * 100
  const energyCv   = (m.energy_cv    ?? 0) * 100
  const facePct    = (m.face_visible_ratio  ?? 0) * 100
  const forwardPct = (m.head_forward_ratio  ?? 0) * 100
  const hasFace    = m.face_visible_ratio != null

  const fillerEvts    = timeline.filter(e => e.event_type === 'filler_word')
  const corrEvts      = timeline.filter(e => e.event_type === 'self_correction')
  const aggTimeline   = timeline.filter(e => !['filler_word','self_correction'].includes(e.event_type))

  const pid     = report.id
  const dateStr = new Date(report.processed_at ?? report.uploaded_at)
    .toLocaleDateString('es-CL', { day: 'numeric', month: 'short', year: 'numeric' })

  return (
    <div className="min-h-screen bg-[#F4F4F8]">
      {/* Header */}
      <header className="bg-white border-b border-[#E4E4EE] px-6 py-4 flex items-center gap-4 sticky top-0 z-30 shadow-sm">
        <IFLogo size="sm" />
        <div className="flex-1 min-w-0 ml-2">
          <h1 className="text-sm font-semibold text-[#0C0C18] truncate">{report.title}</h1>
          <p className="text-xs text-[#9090A8]">{report.language === 'es' ? 'Español' : 'English'} · {(dur/60).toFixed(1)} min · {dateStr}</p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <Link to={`/dashboard/${pid}`} className="text-xs font-medium text-[#1A5FFF] hover:underline underline-offset-4">
            Dashboard →
          </Link>
          <Link to="/history" className="text-xs text-[#9090A8] hover:text-[#0C0C18] transition-colors">Historial</Link>
          <Link to="/" className="text-xs text-[#9090A8] hover:text-[#0C0C18] transition-colors">+ Nueva</Link>
          <span className="text-xs px-2.5 py-1 rounded-full bg-[#D1FAE5] text-[#059669] font-semibold">Completo</span>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex gap-8">

          {/* Sidebar */}
          <Sidebar
            active={activeSection}
            onSelect={setActiveSection}
            hasVision={hasFace}
            hasFeedback={feedback.length > 0}
            hasTimeline={aggTimeline.length > 0}
            hasTranscript={transcript.length > 0}
          />

          {/* Main content */}
          <div className="flex-1 min-w-0 space-y-16">

            {/* VOZ Y AUDIO */}
            <section id="voz" className="scroll-mt-28">
              <p className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#9090A8] mb-8">Voz y audio</p>

              {/* Hero stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-8 mb-10 p-6 bg-white rounded-2xl border border-[#EBEBF4] shadow-sm">
                <BigStat label="Velocidad" value={m.avg_wpm ?? 0} unit="PPM" sub="ref. 120–150" delay={0}
                  help="Palabras Por Minuto: cuántas palabras dices en promedio cada minuto. Entre 120 y 150 es ideal para presentaciones. Menos de 100 puede sentirse lento; más de 180 es difícil de seguir." />
                <BigStat label="Silencio" value={silencePct} unit="%" sub="del tiempo total" delay={80}
                  help="Porcentaje del tiempo sin habla detectada. Un 15–25% es normal y da ritmo al discurso. Demasiado silencio puede indicar nerviosismo; muy poco no da espacio al oyente para procesar." />
                <BigStat label="Muletillas" value={m.filler_count ?? 0} sub={`${(m.filler_rate_per_min ?? 0).toFixed(1)}/min`} delay={160}
                  help='Palabras o sonidos repetidos sin valor semántico (ej. "este", "o sea", "mmm"). Menos de 2 por minuto es excelente. Más de 4/min empieza a distraer al oyente.' />
                <BigStat label="Palabras" value={m.total_words ?? 0} delay={240}
                  help="Total de palabras reconocidas en el audio. Combinado con la duración te dice qué tan denso fue el contenido de tu presentación." />
              </div>

              {/* Secondary stats */}
              <div className="grid grid-cols-2 gap-x-8 bg-white rounded-2xl border border-[#EBEBF4] shadow-sm px-6 py-2">
                <SmallStat label="Pausas ≥ 0.5s" value={String(Math.round(m.pause_count ?? 0))} sub={`promedio ${(m.avg_pause_duration ?? 0).toFixed(1)}s · máx ${(m.max_pause_duration ?? 0).toFixed(1)}s`}
                  help="Interrupciones del habla de al menos medio segundo. Las pausas bien usadas generan énfasis y dan tiempo al oyente para absorber lo dicho. Muchas pausas largas pueden indicar inseguridad." />
                <SmallStat label="Variabilidad velocidad" value={(m.wpm_std ?? 0).toFixed(0)} unit="σ PPM" sub="menor = más estable"
                  help="Desviación estándar (σ) de la velocidad: cuánto fluctúa tu ritmo. Un valor bajo significa ritmo constante; uno alto, que aceleraste y frenaste mucho. Cierta variación es natural y mantiene la atención." />
                <SmallStat label="Variabilidad volumen" value={energyCv.toFixed(1)} unit="% CV" sub="mayor = más dinámico"
                  help="Coeficiente de Variación (CV) del volumen: qué tan dinámico es tu tono. Valores altos indican más expresividad vocal. Muy bajo (menos de 15%) puede sonar monótono; muy alto puede cansar." />
                <SmallStat label="Auto-correcciones" value={String(corrEvts.length)} sub="errores detectados y reparados"
                  help='Veces que detectaste un error en lo que dijiste y te corregiste (ej. "perdón", "quise decir", "me equivoqué"). Algunas correcciones son naturales; muchas pueden indicar falta de preparación.' />
              </div>

              <FillerChips pid={pid} fillers={fillerEvts} corrections={corrEvts} />
            </section>

            {/* PRESENCIA VISUAL */}
            {hasFace && (
              <section id="visual" className="scroll-mt-28">
                <p className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#9090A8] mb-8">Presencia visual</p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-8 p-6 bg-white rounded-2xl border border-[#EBEBF4] shadow-sm">
                  <BigStat label="Cara visible" value={facePct} unit="%" sub="frames detectados" delay={0}
                    help="En qué porcentaje de los fotogramas del video MediaPipe detectó tu rostro. Un valor bajo puede significar que saliste del encuadre, hubo mala iluminación o la cámara estuvo tapada." />
                  <BigStat label="Al frente" value={forwardPct} unit="%" sub="|yaw|<20° y |pitch|<20°" delay={80}
                    help="Porcentaje del tiempo con la cabeza orientada directamente a cámara: menos de 20° de giro horizontal (yaw) y menos de 20° vertical (pitch). Indica cuánto tiempo miraste al interlocutor." />
                  <BigStat label="Yaw medio" value={Math.abs(m.head_yaw_mean ?? 0)} unit="°" sub={`desv. ±${(m.head_yaw_std ?? 0).toFixed(1)}°`} delay={160}
                    help="Yaw es el giro horizontal de la cabeza: izquierda/derecha. 0° = mirando directo a la cámara. El valor promedio muestra hacia dónde tendiste a girar. La desviación (±) indica cuánto variaron tus movimientos: pequeña = cabeza estable; grande = te moviste bastante." />
                  <BigStat label="Pitch medio" value={Math.abs(m.head_pitch_mean ?? 0)} unit="°" sub={`desv. ±${(m.head_pitch_std ?? 0).toFixed(1)}°`} delay={240}
                    help="Pitch es la inclinación vertical de la cabeza: arriba/abajo. 0° = cabeza recta. Valores altos indican que miraste frecuentemente hacia arriba (ej. leyendo notas en pantalla) o hacia abajo. La desviación (±) indica cuánto varió ese movimiento." />
                </div>
                <p className="text-[11px] text-[#CCCCDE] mt-3 px-1">Confianza 0.75–0.9 · MediaPipe landmarks · sin inferencia de intención</p>
              </section>
            )}

            {/* RÚBRICA */}
            {rubric.length > 0 && (
              <section id="rubrica" className="scroll-mt-28">
                <p className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#9090A8] mb-8">Rúbrica v1.0</p>
                <div className="bg-white rounded-2xl border border-[#EBEBF4] shadow-sm px-6 py-2">
                  {rubric.map((r, i) => <RubricRow key={i} r={r} delay={i * 80} />)}
                </div>
                <p className="text-[11px] text-[#CCCCDE] mt-3 px-1">
                  Scores calculados desde métricas medidas — no representan un juicio de valor
                </p>
              </section>
            )}

            {/* FEEDBACK */}
            <section id="feedback" className="scroll-mt-28">
              <p className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#9090A8] mb-8">Retroalimentación</p>
              <FeedbackBlock items={feedback} pid={pid} />
            </section>

            {/* EVENTOS */}
            {aggTimeline.length > 0 && (
              <section id="eventos" className="scroll-mt-28">
                <p className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#9090A8] mb-5">
                  Eventos — clic para ver en video
                </p>
                <div className="space-y-2">
                  {aggTimeline.map((e, i) => <EventCard key={i} evt={e} pid={pid} i={i} />)}
                </div>
              </section>
            )}

            {/* TRANSCRIPCIÓN */}
            {transcript.length > 0 && (
              <section id="transcript" className="scroll-mt-28">
                <p className="text-[11px] font-bold tracking-[0.2em] uppercase text-[#9090A8] mb-5">Transcripción</p>
                <div className="bg-white border border-[#EBEBF4] rounded-2xl shadow-sm p-6 max-h-80 overflow-y-auto space-y-4">
                  {transcript.map((seg, i) => (
                    <div key={i} className="flex gap-4 group">
                      <Link
                        to={`/dashboard/${pid}?t=${seg.start_seconds.toFixed(1)}`}
                        className="font-mono text-[11px] text-[#1A5FFF] w-10 flex-shrink-0 pt-0.5 hover:underline"
                      >
                        {tc(seg.start_seconds)}
                      </Link>
                      <p className="text-sm text-[#2C2C3E] leading-relaxed">{seg.text}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <p className="text-[11px] text-[#CCCCDE] text-center pb-8">
              Análisis basado en datos medidos · claude-haiku-4-5-20251001 · PI v1.0
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
