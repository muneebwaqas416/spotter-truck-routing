import { X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { RiskChip } from '@/components/ui/RiskChip'
import { formatClock, formatDateTime, formatRate, truncate } from '@/lib/format'
import type { Checkpoint } from '@/redux/types'

interface CheckpointPopupProps {
  checkpoint: Checkpoint
  routeLabel: string
  /** Trip times are shown in the origin's zone. */
  timeZone: string
  onClose: () => void
}

export function CheckpointPopup({
  checkpoint,
  routeLabel,
  timeZone,
  onClose,
}: CheckpointPopupProps) {
  const { weather } = checkpoint
  const unknown = checkpoint.risk === 'UNKNOWN'
  return (
    <div className="relative w-72 space-y-3 p-3 text-sm">
      {/* 0.5rem from the top and 1.25rem in from the right edge, inside the card. */}
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label="Close checkpoint details"
        onClick={onClose}
        className="absolute top-2 right-5 text-muted-foreground"
      >
        <X />
      </Button>

      <div className="space-y-1.5 pr-10">
        <p className="tabular font-mono text-xs text-muted-foreground">
          Checkpoint {checkpoint.index} · mi {Math.round(checkpoint.mile)}
        </p>
        <div className="flex items-center gap-2">
          <p className="font-semibold text-foreground">{routeLabel}</p>
          <RiskChip level={checkpoint.risk} />
        </div>
      </div>

      <div className="tabular rounded-md bg-muted/50 px-2.5 py-2 font-mono text-xs">
        <div className="flex justify-between">
          <span className="text-muted-foreground">ETA</span>
          <span className="font-semibold text-foreground">
            {formatDateTime(checkpoint.eta, timeZone)}
          </span>
        </div>
        {weather.forecast_time && (
          <div className="flex justify-between">
            <span className="text-muted-foreground">Forecast hour</span>
            <span>{formatClock(weather.forecast_time, timeZone)}</span>
          </div>
        )}
      </div>

      {unknown ? (
        <p className="rounded-md border border-dashed border-input px-2.5 py-2 text-xs text-muted-foreground">
          Forecast unavailable for this time. This stretch is not assumed safe.
        </p>
      ) : (
        <dl className="tabular grid grid-cols-3 gap-2 font-mono text-xs">
          <Cell
            label="Wind"
            value={weather.wind_mph === null ? '—' : `${truncate(weather.wind_mph, 1)} mph`}
            sub={weather.gust_mph === null ? undefined : `gusts ${truncate(weather.gust_mph, 1)}`}
          />
          <Cell label="Rain" value={formatRate(weather.rain_in_hr, 'in/h')} />
          <Cell label="Snow" value={formatRate(weather.snow_in_hr, 'in/h', 1)} />
        </dl>
      )}

      {checkpoint.reasons.length > 0 && (
        <ul className="space-y-1 text-xs text-foreground">
          {checkpoint.reasons.map((reason) => (
            <li key={reason}>• {reason}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Cell({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-md border border-border px-2 py-1.5">
      <dt className="text-2xs text-muted-foreground uppercase">{label}</dt>
      <dd className="font-semibold text-foreground">{value}</dd>
      {sub && <dd className="text-2xs text-muted-foreground">{sub}</dd>}
    </div>
  )
}
