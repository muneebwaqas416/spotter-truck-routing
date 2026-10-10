import { RotateCw, Timer, WifiOff } from 'lucide-react'
import { useEffect, useState } from 'react'

import type { ApiError } from '@/redux/errors'
import { StatusAlert } from '@/components/StatusAlert'
import { Button } from '@/components/ui/button'

import { describeError } from './describeError'

interface ErrorAlertProps {
  error: ApiError
  onRetry: () => void
}

export function ErrorAlert({ error, onRetry }: ErrorAlertProps) {
  const description = describeError(error)
  const [showDetails, setShowDetails] = useState(false)
  const waitSeconds = useCountdown(error.status === 429 ? (error.retryAfterSeconds ?? 30) : 0)

  const icon = error.status === 'NETWORK_ERROR' ? WifiOff : error.status === 429 ? Timer : undefined

  return (
    <StatusAlert
      role="alert"
      tone={description.tone}
      icon={icon}
      title={description.title}
      actions={
        description.retryable && (
          <>
            <Button
              size="sm"
              variant={description.tone === 'danger' ? 'destructive' : 'outline'}
              onClick={onRetry}
              disabled={waitSeconds > 0}
            >
              <RotateCw aria-hidden className="size-3.5" />
              {waitSeconds > 0
                ? `Try again in 0:${String(waitSeconds).padStart(2, '0')}`
                : 'Try again'}
            </Button>
            <Button
              variant="link"
              size="sm"
              className="text-current"
              aria-expanded={showDetails}
              onClick={() => setShowDetails((value) => !value)}
            >
              Details
            </Button>
          </>
        )
      }
    >
      <p>{description.body}</p>
      {showDetails && (
        <p className="mt-2 rounded-md bg-white/60 px-2 py-1 font-mono text-xs">
          {String(error.status)}
          {error.code ? ` · ${error.code}` : ''}
        </p>
      )}
    </StatusAlert>
  )
}

/** Counts down from `seconds` once; callers remount (via `key`) to restart it. */
function useCountdown(seconds: number): number {
  const [remaining, setRemaining] = useState(seconds)
  useEffect(() => {
    if (seconds <= 0) return
    const timer = setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000)
    return () => clearInterval(timer)
  }, [seconds])
  return remaining
}
