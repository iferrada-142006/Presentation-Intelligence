import { useState, useCallback, DragEvent, ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadPresentation, getStatus } from '../lib/api'
import { usePolling } from '../hooks/usePolling'
import IFLogo from '../components/IFLogo'

type Phase = 'idle' | 'uploading' | 'processing' | 'done' | 'error'

const STAGE_LABELS: Record<string, string> = {
  extract:  'Extrayendo audio',
  speech:   'Transcribiendo voz',
  audio:    'Analizando audio',
  vision:   'Analizando presencia visual',
  features: 'Detectando eventos',
  rubric:   'Calculando rúbrica',
  feedback: 'Generando retroalimentación',
}

export default function HomePage() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<Phase>('idle')
  const [dragOver, setDragOver] = useState(false)
  const [title, setTitle] = useState('')
  const [language, setLanguage] = useState('es')
  const [presentationId, setPresentationId] = useState<number | null>(null)
  const [progress, setProgress] = useState(0)
  const [stageLabel, setStageLabel] = useState('')
  const [error, setError] = useState('')

  const doUpload = useCallback(async (file: File) => {
    setPhase('uploading')
    setError('')
    try {
      const res = await uploadPresentation(file, title || file.name, language)
      setPresentationId(res.id)
      setPhase('processing')
    } catch (e) {
      setError((e as Error).message)
      setPhase('error')
    }
  }, [title, language])

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) doUpload(file)
  }, [doUpload])

  const handleFile = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) doUpload(file)
  }, [doUpload])

  usePolling(async () => {
    if (!presentationId) return
    const status = await getStatus(presentationId)
    if (status.job) {
      setProgress(status.job.progress_pct)
      setStageLabel(STAGE_LABELS[status.job.current_stage ?? ''] ?? '')
    }
    if (status.status === 'complete') {
      setPhase('done')
      setTimeout(() => navigate(`/report/${presentationId}`), 600)
    } else if (status.status === 'failed') {
      setPhase('error')
      setError('El procesamiento falló. Intenta con otro video.')
    }
  }, 3000, phase === 'processing')

  return (
    <div className="min-h-screen bg-[#F4F4F8] flex flex-col">
      {/* Nav */}
      <header className="flex items-center justify-between px-8 py-5 bg-white border-b border-[#E4E4EE]">
        <div className="flex items-center gap-2.5">
          <IFLogo size="sm" />
          <span className="text-xs tracking-[0.15em] text-[#9090A8] uppercase font-medium">
            Presentation Intelligence
          </span>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-md">

          {phase === 'idle' && (
            <div className="space-y-8">
              <div>
                <h1 className="text-3xl font-semibold text-[#0C0C18] leading-tight">
                  Analiza tu<br />presentación
                </h1>
                <p className="text-[#6868848] text-sm mt-3 leading-relaxed text-[#686882]">
                  Voz, ritmo y presencia visual medidos con precisión.
                  Retroalimentación basada en datos, no en suposiciones.
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex gap-2">
                  <input
                    className="flex-1 bg-white border border-[#DCDCEC] rounded-lg px-4 py-3 text-sm text-[#0C0C18] placeholder-[#B0B0C8] focus:outline-none focus:border-[#1A5FFF] transition-colors"
                    placeholder="Título (opcional)"
                    value={title}
                    onChange={e => setTitle(e.target.value)}
                  />
                  <select
                    className="bg-white border border-[#DCDCEC] rounded-lg px-3 py-3 text-sm text-[#0C0C18] focus:outline-none focus:border-[#1A5FFF] transition-colors"
                    value={language}
                    onChange={e => setLanguage(e.target.value)}
                  >
                    <option value="es">ES</option>
                    <option value="en">EN</option>
                  </select>
                </div>

                <div
                  onDrop={handleDrop}
                  onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                  onDragLeave={() => setDragOver(false)}
                  className={[
                    'relative border-2 border-dashed rounded-lg px-8 py-12 text-center cursor-pointer transition-all',
                    dragOver
                      ? 'border-[#1A5FFF] bg-[#EEF3FF]'
                      : 'border-[#DCDCEC] bg-white hover:border-[#ABABC8]',
                  ].join(' ')}
                >
                  <input
                    type="file"
                    accept="video/mp4,video/webm,video/quicktime,.avi,.mkv"
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    onChange={handleFile}
                  />
                  <p className="text-[#0C0C18] font-medium text-sm">Arrastra tu video aquí</p>
                  <p className="text-[#B0B0C8] text-xs mt-1.5">o haz clic para seleccionar</p>
                  <p className="text-[#CCCCDE] text-xs mt-4">MP4 · WebM · MOV · hasta 512 MB</p>
                </div>
              </div>
            </div>
          )}

          {phase === 'uploading' && (
            <div className="space-y-4 py-12">
              <div className="h-0.5 bg-[#1A5FFF] animate-pulse rounded-full" />
              <p className="text-[#686882] text-sm">Subiendo video…</p>
            </div>
          )}

          {phase === 'processing' && (
            <div className="py-10 space-y-5">
              <div>
                <div className="flex justify-between items-baseline mb-2">
                  <p className="text-[#0C0C18] font-medium text-sm">Procesando</p>
                  <span className="text-[#1A5FFF] text-sm font-semibold tabular-nums">{progress}%</span>
                </div>
                <div className="h-1 bg-[#E4E4EE] rounded-full overflow-hidden">
                  <div
                    className="h-1 bg-[#1A5FFF] rounded-full transition-all duration-700"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
              {stageLabel && <p className="text-[#686882] text-sm">{stageLabel}…</p>}
              <p className="text-[#ABABC8] text-xs">Puede tomar varios minutos según la duración del video</p>
            </div>
          )}

          {phase === 'done' && (
            <div className="space-y-3 py-12">
              <div className="h-0.5 bg-[#1A5FFF] rounded-full" />
              <p className="text-[#686882] text-sm">Análisis completo. Cargando reporte…</p>
            </div>
          )}

          {phase === 'error' && (
            <div className="py-10 space-y-4">
              <div className="h-0.5 bg-[#EF4444] rounded-full" />
              <p className="text-[#EF4444] text-sm">{error}</p>
              <button
                className="text-xs text-[#686882] hover:text-[#0C0C18] transition-colors underline underline-offset-4"
                onClick={() => { setPhase('idle'); setError(''); setProgress(0) }}
              >
                Intentar de nuevo
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
