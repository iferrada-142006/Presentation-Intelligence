/**
 * FaceMeshOverlay
 *
 * Loads MediaPipe Face Mesh from jsDelivr CDN via <script> tags (avoids Vite/WASM
 * bundling issues with the npm package). Draws face tessellation + iris landmarks
 * on a <canvas> overlaid on the video, throttled to ~5 fps.
 */
import { useEffect, useRef, useState, useCallback } from 'react'

const CDN   = 'https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh@0.4.1633559619'
const DRAW  = 'https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils@0.3.1620248257'

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) { resolve(); return }
    const el = document.createElement('script')
    el.src = src
    el.crossOrigin = 'anonymous'
    el.onload  = () => resolve()
    el.onerror = () => reject(new Error(`Failed to load ${src}`))
    document.head.appendChild(el)
  })
}

// Singleton — created once, reused across re-renders
let _fm: any = null
let _loading: Promise<any> | null = null

async function getModel(): Promise<any> {
  if (_fm) return _fm
  if (_loading) return _loading

  _loading = (async () => {
    await loadScript(`${DRAW}/drawing_utils.js`)
    await loadScript(`${CDN}/face_mesh.js`)

    const win = window as any
    const fm = new win.FaceMesh({
      locateFile: (f: string) => `${CDN}/${f}`,
    })
    fm.setOptions({
      maxNumFaces: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    })
    _fm = fm
    return fm
  })()

  return _loading
}

interface Props {
  videoRef: React.RefObject<HTMLVideoElement | null>
}

export default function FaceMeshOverlay({ videoRef }: Props) {
  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const rafRef     = useRef<number>(0)
  const lastMsRef  = useRef<number>(0)
  const fmRef      = useRef<any>(null)

  const [enabled, setEnabled] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  // Draw MediaPipe results on canvas
  const onResults = useCallback((results: any) => {
    const canvas = canvasRef.current
    const video  = videoRef.current
    if (!canvas || !video) return

    canvas.width  = video.videoWidth  || video.clientWidth
    canvas.height = video.videoHeight || video.clientHeight

    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    if (!results.multiFaceLandmarks?.length) return

    const win  = window as any
    const lms  = results.multiFaceLandmarks[0]

    // Tessellation (full mesh)
    if (win.drawConnectors && win.FACEMESH_TESSELATION) {
      win.drawConnectors(ctx, lms, win.FACEMESH_TESSELATION, {
        color: 'rgba(0,220,130,0.20)',
        lineWidth: 0.6,
      })
    }

    // Contours (lips, eyes, eyebrows)
    const contourSets = [
      win.FACEMESH_RIGHT_EYE, win.FACEMESH_LEFT_EYE,
      win.FACEMESH_RIGHT_EYEBROW, win.FACEMESH_LEFT_EYEBROW,
      win.FACEMESH_LIPS, win.FACEMESH_FACE_OVAL,
    ].filter(Boolean)
    for (const conn of contourSets) {
      win.drawConnectors(ctx, lms, conn, { color: 'rgba(0,255,140,0.55)', lineWidth: 1 })
    }

    // Iris (landmarks 468–477)
    if (lms.length >= 478) {
      const W = canvas.width, H = canvas.height
      ctx.fillStyle = 'rgba(255, 210, 0, 0.9)'
      for (let i = 468; i < 478; i++) {
        const p = lms[i]
        ctx.beginPath()
        ctx.arc(p.x * W, p.y * H, 2.5, 0, Math.PI * 2)
        ctx.fill()
      }
    }
  }, [videoRef])

  // RAF loop — throttled to ~5fps
  const startLoop = useCallback((fm: any) => {
    const tick = async (now: number) => {
      if (!fmRef.current) return  // disabled
      const video = videoRef.current
      if (video && !video.paused && !video.ended && now - lastMsRef.current > 200) {
        lastMsRef.current = now
        try { await fm.send({ image: video }) } catch (_) { /* skip frame */ }
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
  }, [videoRef])

  const enable = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const fm = await getModel()
      fm.onResults(onResults)
      fmRef.current = fm
      startLoop(fm)
      setEnabled(true)
    } catch (e) {
      console.error(e)
      setError('No se pudo cargar MediaPipe')
    } finally {
      setLoading(false)
    }
  }, [onResults, startLoop])

  const disable = useCallback(() => {
    fmRef.current = null
    cancelAnimationFrame(rafRef.current)
    const canvas = canvasRef.current
    if (canvas) canvas.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height)
    setEnabled(false)
  }, [])

  useEffect(() => () => { fmRef.current = null; cancelAnimationFrame(rafRef.current) }, [])

  return (
    <>
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full pointer-events-none rounded-lg"
        style={{ display: enabled ? 'block' : 'none' }}
      />

      <button
        onClick={enabled ? disable : enable}
        disabled={loading}
        title={enabled ? 'Desactivar landmarks' : 'Activar landmarks de cara e iris'}
        className={[
          'absolute top-2 right-2 z-10 text-[11px] font-semibold px-2.5 py-1.5 rounded-lg transition-all select-none',
          enabled  ? 'bg-[#00DC82] text-[#0C2010] shadow-md'
                   : 'bg-black/50 text-white hover:bg-black/70',
          loading  ? 'opacity-60 cursor-wait' : 'cursor-pointer',
        ].join(' ')}
      >
        {loading ? 'Cargando…' : enabled ? '● Landmarks' : '○ Landmarks'}
      </button>

      {error && (
        <p className="absolute bottom-10 left-2 right-2 text-[10px] text-white bg-red-500/80 px-2 py-1 rounded z-10">
          {error}
        </p>
      )}
    </>
  )
}
