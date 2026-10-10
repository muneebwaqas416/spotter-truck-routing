import { useEffect, useState } from 'react'

/** Seconds since the calling component mounted. */
export function useElapsedSeconds(): number {
  const [startedAt] = useState(() => Date.now())
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setElapsed((Date.now() - startedAt) / 1000), 250)
    return () => clearInterval(timer)
  }, [startedAt])
  return elapsed
}
