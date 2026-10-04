import { useState, useEffect } from 'react'

export function useCountUp(target: number, duration = 900, decimals = 0): string {
  const [value, setValue] = useState(0)

  useEffect(() => {
    if (target === 0) return
    const start = performance.now()
    let raf: number

    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3) // easeOutCubic
      setValue(eased * target)
      if (progress < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])

  return value.toFixed(decimals)
}
