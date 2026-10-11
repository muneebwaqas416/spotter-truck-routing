import { Ban, CloudOff } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { RISK_STYLES } from '@/lib/risk'

import type { RouteOption } from '@/redux/types'
import { addSeconds, formatClock, formatDuration, formatMiles } from '@/lib/format'

import { milesAt } from './derive'
import { RiskBar } from './RiskBar'
import { cn } from '@/lib/utils'

interface RouteCardProps {
  route: RouteOption
  departureTime: string
  /** Arrival times are shown in the destination's zone. */
  arrivalTimeZone: string
  selected: boolean
  badge?: 'recommended' | 'least-risky'
  isFastest: boolean
  onSelect: () => void
}

const BADGES = {
  recommended: { text: 'Recommended', variant: 'success' },
  'least-risky': { text: 'Least risky', variant: 'purple' },
} as const

export function RouteCard({
  route,
  departureTime,
  arrivalTimeZone,
  selected,
  badge,
  isFastest,
  onSelect,
}: RouteCardProps) {
  const noTravel = milesAt(route, 'NO_TRAVEL')
  const unknown = milesAt(route, 'UNKNOWN')
  // Selection always uses the primary colour; the badge carries the status.
  const borderClass = selected
    ? 'border-primary ring-1 ring-primary'
    : 'border-border hover:border-input'

  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        'w-full space-y-3 rounded-lg border bg-white p-4 text-left transition-colors',
        borderClass,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className={cn(
              'size-3 rounded-full border-2',
              selected ? 'border-primary bg-primary' : 'border-input',
            )}
          />
          <span className="font-semibold text-foreground">{route.label}</span>
        </div>
        <div className="flex gap-1.5">
          {badge && (
            <Badge variant={BADGES[badge].variant} className="uppercase">
              {BADGES[badge].text}
            </Badge>
          )}
          {isFastest && (
            <Badge variant="secondary" className="uppercase">
              Fastest
            </Badge>
          )}
        </div>
      </div>

      <div className="tabular flex items-baseline justify-between font-mono text-sm">
        <span className="text-base font-semibold text-foreground">
          {formatMiles(route.metrics.distance_mi)}
        </span>
        <span className="text-foreground">
          <span className="font-semibold text-foreground">
            {formatDuration(route.metrics.duration_s)}
          </span>
          <span className="ml-2 text-xs text-muted-foreground">
            ETA {formatClock(addSeconds(departureTime, route.metrics.duration_s), arrivalTimeZone)}
          </span>
        </span>
      </div>

      <RiskBar route={route} />

      <dl className="tabular grid grid-cols-4 gap-1 font-mono text-xs">
        <Stat
          label="No Travel"
          value={noTravel}
          color={noTravel > 0 ? RISK_STYLES.NO_TRAVEL.color : undefined}
        />
        <Stat
          label="Severe"
          value={milesAt(route, 'SEVERE')}
          color={milesAt(route, 'SEVERE') > 0 ? RISK_STYLES.SEVERE.color : undefined}
        />
        <Stat
          label="High"
          value={milesAt(route, 'HIGH')}
          color={milesAt(route, 'HIGH') > 0 ? RISK_STYLES.HIGH.color : undefined}
        />
        <div>
          <dt className="text-muted-foreground">Avg risk</dt>
          <dd className="font-semibold text-foreground">
            {route.metrics.avg_risk?.toFixed(1) ?? '—'}
          </dd>
        </div>
      </dl>

      {(noTravel > 0 || unknown > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {noTravel > 0 && (
            <Badge variant="purple">
              <Ban aria-hidden /> No Travel {Math.round(noTravel)} mi
            </Badge>
          )}
          {unknown > 0 && (
            <Badge variant="outline" className="bg-muted/50 text-muted-foreground">
              <CloudOff aria-hidden /> Unknown {Math.round(unknown)} mi
            </Badge>
          )}
        </div>
      )}
    </button>
  )
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-semibold text-foreground" style={color ? { color } : undefined}>
        {Math.round(value)} mi
      </dd>
    </div>
  )
}
