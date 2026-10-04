import { useState, useCallback, DragEvent, ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadPresentation, getStatus } from '../lib/api'
import { usePolling } from '../hooks/usePolling'

type Phase = 'idle' | 'uploading' | 'processing' | 'done' | 'error'

const STAGE_LABELS: Record<string, string> = {
  extract:  'Extrayendo audio…',
  speech:   'Transcribiendo voz…',
  audio:    'Analizando audio…',
  vision:   'Analizando presencia visual…',
  features: 'Detectando eventos en el tiempo…',
  feedback: 'Generando retroalimentación con IA…',
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
      setTimeout(() => navigate(`/report/${presentationId}`), 800)
    } else if (status.status === 'failed') {
      setPhase('error')
      setError('El procesamiento falló. Intenta con otro video.')
    }
  }, 3000, phase === 'processing')

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-lg">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2">
            Presentation Intelligence
          </h1>
          <p className="text-gray-400 text-sm">
            Análisis multimodal basado en evidencia. Sin inferencias sin datos.
          </p>
        </div>

        {phase === 'idle' && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <input
                className="col-span-2 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Título (opcional)"
                value={title}
                onChange={e => setTitle(e.target.value)}
              />
              <select
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={language}
                onChange={e => setLanguage(e.target.value)}
              >
                <option value="es">Español</option>
                <option value="en">English</option>
              </select>
            </div>

            <div
              onDrop={handleDrop}
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              className={[
                'relative border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors',
                dragOver
                  ? 'border-indigo-500 bg-indigo-950'
                  : 'border-gray-700 bg-gray-900 hover:border-gray-500',
              ].join(' ')}
            >
              <input
                type="file"
                accept="video/mp4,video/webm,video/quicktime,.avi,.mkv"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={handleFile}
              />
              <div className="text-4xl mb-3">🎬</div>
              <p className="text-gray-300 font-medium">Arrastra tu video aquí</p>
              <p className="text-gray-500 text-sm mt-1">o haz clic para seleccionar</p>
              <p className="text-gray-600 text-xs mt-3">MP4 · WebM · MOV · AVI · MKV — hasta 512 MB</p>
            </div>
          </div>
        )}

        {phase === 'uploading' && (
          <div className="text-center py-16">
            <div className="text-5xl mb-4 animate-bounce">⬆️</div>
            <p className="text-gray-300">Subiendo video…</p>
          </div>
        )}

        {phase === 'processing' && (
          <div className="text-center py-12 space-y-5">
            <div className="text-5xl animate-spin inline-block">⚙️</div>
            <p className="text-gray-300 font-medium text-lg">Procesando presentación</p>
            {stageLabel && <p className="text-indigo-400 text-sm">{stageLabel}</p>}
            <div className="w-full bg-gray-800 rounded-full h-2.5">
              <div
                className="bg-indigo-500 h-2.5 rounded-full transition-all duration-700"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-gray-600 text-xs">Esto puede tomar varios minutos según la duración del video</p>
          </div>
        )}

        {phase === 'done' && (
          <div className="text-center py-16">
            <div className="text-5xl mb-4">✅</div>
            <p className="text-gray-300">Análisis completo. Cargando reporte…</p>
          </div>
        )}

        {phase === 'error' && (
          <div className="text-center py-10 space-y-4">
            <div className="text-5xl mb-2">❌</div>
            <p className="text-red-400">{error}</p>
            <button
              className="px-6 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-200 transition-colors"
              onClick={() => { setPhase('idle'); setError(''); setProgress(0) }}
            >
              Intentar de nuevo
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
