import { CircleAlert, Pause, Play, RotateCw, TriangleAlert } from 'lucide-react'
import { useEffect, useId, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Spinner } from '@/components/ui/spinner'
import { MAX_FORECAST_HOUR } from '@/features/trip/tripSlice'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

interface ForecastSliderProps {
  start: string
  hour: number
  onHourChange: (hour: number) => void
  isLoading: boolean
  hasError: boolean
  onRetry: () => void
  missingByHour: number[]
}

const TICKS = [0, 6, 12, 18, 24, 30, 36, 42, 48]
const PLAY_STEP_MS = 600

export function ForecastSlider({
  start,
  hour,
  onHourChange,
  isLoading,
  hasError,
  onRetry,
  missingByHour,
}: ForecastSliderProps) {
  const id = useId()
  const [playing, setPlaying] = useState(false)
  const disabled = isLoading || hasError
  const at = new Date(new Date(start).getTime() + hour * 3_600_000).toISOString()
  const missingNow = missingByHour[hour] ?? 0

  useEffect(() => {
    if (!playing || disabled || hour >= MAX_FORECAST_HOUR) return
    const timer = setTimeout(() => {
      const next = hour + 1
      onHourChange(next)
      if (next >= MAX_FORECAST_HOUR) setPlaying(false)
    }, PLAY_STEP_MS)
    return () => clearTimeout(timer)
  }, [playing, hour, disabled, onHourChange])

  return (
    <Card className="w-full max-w-3xl gap-0 bg-white/95 backdrop-blur">
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="icon-lg"
            className="rounded-full"
            aria-label={playing ? 'Pause forecast animation' : 'Play forecast animation'}
            disabled={disabled}
            onClick={() => {
              if (hour >= MAX_FORECAST_HOUR) onHourChange(0)
              setPlaying((value) => !value)
            }}
          >
            {playing ? <Pause /> : <Play />}
          </Button>
          <Label htmlFor={id} className="text-base font-semibold">
            Forecast timeline
          </Label>
          <Badge
            variant="outline"
            className="tabular border-primary/20 bg-primary/5 font-mono text-primary"
          >
            +{hour}h · {formatDateTime(at)}
          </Badge>
          <div className="ml-auto flex gap-1">
            <Button
              variant="outline"
              size="sm"
              className="font-mono"
              disabled={disabled || hour <= 0}
              onClick={() => onHourChange(hour - 1)}
            >
              −1h
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="font-mono"
              disabled={disabled || hour >= MAX_FORECAST_HOUR}
              onClick={() => onHourChange(hour + 1)}
            >
              +1h
            </Button>
          </div>
        </div>

        <div className="space-y-1.5">
          <Slider
            id={id}
            min={0}
            max={MAX_FORECAST_HOUR}
            step={1}
            value={[hour]}
            disabled={disabled}
            aria-valuetext={`Plus ${hour} hours, ${formatDateTime(at)}`}
            // The default muted track is too faint over the translucent card.
            className="**:data-[slot=slider-track]:bg-border"
            onValueChange={([next]) => next !== undefined && onHourChange(next)}
          />
          {/* Hours with missing forecast data are hatched under the track. */}
          <div aria-hidden className="flex h-1">
            {missingByHour.map((missing, index) => (
              <span key={index} className={cn('flex-1', missing > 0 && 'hatched opacity-60')} />
            ))}
          </div>
          <div
            aria-hidden
            className="tabular flex justify-between font-mono text-2xs text-muted-foreground"
          >
            {TICKS.map((tick) => (
              <span key={tick} className={cn(tick === hour && 'font-semibold text-primary')}>
                {tick === 0 ? '0h' : `+${tick}h`}
              </span>
            ))}
          </div>
        </div>

        <div aria-live="polite" className="min-h-5 text-xs">
          {isLoading && (
            <p className="flex items-center gap-2 text-muted-foreground">
              <Spinner className="size-3.5" /> Loading 48-hour corridor forecast…
            </p>
          )}
          {hasError && (
            <p className="flex items-center gap-2 text-destructive">
              <CircleAlert aria-hidden className="size-3.5" /> Heatmap unavailable — routes are
              still usable.
              <Button
                variant="link"
                size="xs"
                className="h-auto p-0 text-destructive"
                onClick={onRetry}
              >
                <RotateCw aria-hidden /> Retry
              </Button>
            </p>
          )}
          {!isLoading && !hasError && missingNow > 0 && (
            <p className="flex items-center gap-2 text-warning">
              <TriangleAlert aria-hidden className="size-3.5" />
              Forecast missing for {Math.round(missingNow * 100)}% of the area at this hour — shown
              blank, not as safe.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
