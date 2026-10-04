import { useState, useEffect, useCallback } from 'react'

export function useActiveSection(ids: string[]): [string, (id: string) => void] {
  const [active, setActive] = useState(ids[0] ?? '')

  useEffect(() => {
    const observers: IntersectionObserver[] = []

    ids.forEach(id => {
      const el = document.getElementById(id)
      if (!el) return
      const obs = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) setActive(id) },
        { rootMargin: '-20% 0px -60% 0px', threshold: 0 }
      )
      obs.observe(el)
      observers.push(obs)
    })

    return () => observers.forEach(o => o.disconnect())
  }, [ids.join(',')])

  const select = useCallback((id: string) => setActive(id), [])

  return [active, select]
}
