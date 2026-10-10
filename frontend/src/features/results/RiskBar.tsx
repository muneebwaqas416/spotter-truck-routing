import type { RouteOption } from '@/redux/types'
import { RISK_ORDER, RISK_STYLES } from '@/lib/risk'

import { milesAt } from './derive'

/** Stacked bar of route miles by risk level, in route-independent order. */
export function RiskBar({ route }: { route: RouteOption }) {
  const total = RISK_ORDER.reduce((sum, level) => sum + milesAt(route, level), 0)
  const description = RISK_ORDER.filter((level) => milesAt(route, level) > 0)
    .map((level) => `${RISK_STYLES[level].label} ${Math.round(milesAt(route, level))} mi`)
    .join(', ')

  return (
    <div
      role="img"
      aria-label={`Miles by risk: ${description}`}
      className="flex h-2 w-full overflow-hidden rounded-full bg-muted"
    >
      {total > 0 &&
        RISK_ORDER.map((level) => {
          const miles = milesAt(route, level)
          if (miles <= 0) return null
          return (
            <span
              key={level}
              className={level === 'UNKNOWN' ? 'hatched' : undefined}
              style={{
                width: `${(miles / total) * 100}%`,
                backgroundColor: level === 'UNKNOWN' ? undefined : RISK_STYLES[level].color,
              }}
            />
          )
        })}
    </div>
  )
}
