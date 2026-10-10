import { Check } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { useElapsedSeconds } from '@/hooks/useElapsedSeconds'
import { cn } from '@/lib/utils'

/**
 * The analysis is a single request, so step progress is estimated from typical
 * timings; the final step stays active until the response actually arrives.
 */
const STEPS = [
  { label: 'Locating origin & destination', startsAt: 0 },
  { label: 'Fetching 3 truck routes', startsAt: 1.5 },
  { label: 'Checking weather at each checkpoint at its ETA', startsAt: 3.5 },
  { label: 'Scoring risk & ranking routes', startsAt: 7 },
]

export function AnalysisProgress() {
  const elapsed = useElapsedSeconds()
  const activeIndex = STEPS.reduce(
    (active, step, index) => (elapsed >= step.startsAt ? index : active),
    0,
  )

  return (
    <div className="space-y-4">
      <Card role="status" aria-live="polite" className="px-4">
        <ol className="space-y-3">
          {STEPS.map((step, index) => {
            const state =
              index < activeIndex ? 'done' : index === activeIndex ? 'active' : 'pending'
            return (
              <li key={step.label} className="flex items-center gap-3 text-sm">
                <StepIcon state={state} />
                <span
                  className={cn({
                    'font-medium text-primary': state === 'active',
                    'text-foreground': state === 'done',
                    'text-subtle': state === 'pending',
                  })}
                >
                  {step.label}
                </span>
              </li>
            )
          })}
        </ol>
        <p className="mt-4 border-t border-border pt-3 text-center text-xs text-muted-foreground italic">
          Usually takes 5–15 seconds
        </p>
      </Card>

      <div className="space-y-3" aria-hidden>
        <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
          Route options
        </p>
        {[0, 1, 2].map((index) => (
          <Card key={index} size="sm" className="px-3">
            <div className="flex justify-between">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-16" />
            </div>
            <div className="flex gap-2">
              <Skeleton className="h-3 w-14" />
              <Skeleton className="h-3 w-14" />
              <Skeleton className="h-3 w-14" />
            </div>
            <Skeleton className="h-2 w-full" />
          </Card>
        ))}
      </div>
    </div>
  )
}

function StepIcon({ state }: { state: 'done' | 'active' | 'pending' }) {
  if (state === 'done') {
    return (
      <span className="flex size-5 items-center justify-center rounded-full bg-success/10 text-success">
        <Check aria-hidden className="size-3.5" />
      </span>
    )
  }
  if (state === 'active') {
    return (
      <span className="flex size-5 items-center justify-center text-primary">
        <Spinner />
      </span>
    )
  }
  return <span aria-hidden className="size-5 rounded-full border-2 border-border" />
}
