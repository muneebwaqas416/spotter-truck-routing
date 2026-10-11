import { CircleAlert, Route, ServerCrash } from 'lucide-react'
import { useId } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { Switch } from '@/components/ui/switch'
import { HEATMAP_COLOR_RANGE } from '@/lib/risk'

export function EmptyMapCard() {
  return (
    <Card className="pointer-events-auto max-w-sm text-center">
      <CardContent className="space-y-2 py-2">
        <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-muted text-primary">
          <Route aria-hidden className="size-6" />
        </div>
        <h2 className="text-lg font-semibold text-foreground">Your routes will appear here</h2>
        <p className="text-sm text-muted-foreground">
          Fill in the trip form to compare 3 routes by weather risk, load and travel time.
        </p>
      </CardContent>
    </Card>
  )
}

export function MapErrorCard({ title, onRetry }: { title: string; onRetry?: () => void }) {
  return (
    <Card className="pointer-events-auto max-w-sm text-center">
      <CardContent className="space-y-2 py-2">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <ServerCrash aria-hidden className="size-6" />
        </div>
        <h2 className="text-lg font-semibold text-foreground">Routes unavailable</h2>
        <p className="text-sm text-muted-foreground">{title}</p>
        {onRetry && (
          <Button className="mt-2 w-full" size="lg" onClick={onRetry}>
            Try again
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export function LoadingPill() {
  return (
    <div
      role="status"
      className="pointer-events-auto flex items-center gap-2 rounded-full border bg-white px-4 py-2 text-sm text-foreground shadow-md"
    >
      <Spinner className="text-primary" /> Checking forecasts along your routes…
    </div>
  )
}

export type HeatmapStatus = 'ready' | 'loading' | 'error'

interface HeatmapToggleProps {
  enabled: boolean
  status: HeatmapStatus
  /** Why the heatmap failed (shown on hover and to screen readers). */
  errorMessage?: string
  onToggle: (enabled: boolean) => void
  onRetry: () => void
}

/** The switch shows exactly what the map shows: on + status, so "on" never looks like "missing". */
export function HeatmapToggle({
  enabled,
  status,
  errorMessage,
  onToggle,
  onRetry,
}: HeatmapToggleProps) {
  const id = useId()
  const gradient = `linear-gradient(to right, ${HEATMAP_COLOR_RANGE.map(([r, g, b]) => `rgb(${r},${g},${b})`).join(',')})`
  return (
    <div className="pointer-events-auto flex items-center gap-3 rounded-xl border bg-white/95 px-3 py-2 shadow-md">
      {/* aria-labelledby, not <label htmlFor>: only the switch itself toggles, never the text. */}
      <span id={id} className="text-sm font-medium">
        Weather heatmap
      </span>
      <Switch aria-labelledby={id} checked={enabled} onCheckedChange={onToggle} />
      {enabled && status === 'loading' && (
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Spinner className="size-3.5" /> Loading
        </span>
      )}
      {enabled && status === 'error' && (
        <span className="flex items-center gap-1 text-xs text-destructive" title={errorMessage}>
          <CircleAlert aria-hidden className="size-3.5" /> Unavailable
          <Button
            variant="link"
            size="xs"
            className="h-auto p-0 text-destructive"
            onClick={onRetry}
          >
            Retry
          </Button>
        </span>
      )}
      {enabled && status === 'ready' && (
        <div className="hidden items-center gap-1.5 text-2xs text-muted-foreground sm:flex">
          Low
          <span aria-hidden className="h-2 w-20 rounded-full" style={{ background: gradient }} />
          No Travel
        </div>
      )}
    </div>
  )
}
