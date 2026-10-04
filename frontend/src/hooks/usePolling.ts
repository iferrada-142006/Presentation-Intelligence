import { useEffect, useRef } from 'react'

export function usePolling(
  fn: () => Promise<void>,
  intervalMs: number,
  active: boolean,
) {
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    if (!active) return
    const tick = () => fnRef.current()
    tick()
    const id = setInterval(tick, intervalMs)
    return () => clearInterval(id)
  }, [intervalMs, active])
}
