import type { AnalyzeResponse } from '@/redux/types'
import { useAppDispatch, useAppSelector } from '@/redux/hooks'
import { StatusAlert } from '@/components/StatusAlert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { analysisSubmitted, editTrip, routeSelected } from '@/features/trip/tripSlice'
import { formatClock, formatDurationDelta } from '@/lib/format'

import { fastestRouteId, hasNoSafeRoute, recommendedRoute, resultNotices } from './derive'
import { RouteCard } from './RouteCard'

const DELAY_SUGGESTION_HOURS = 6

export function ResultsPanel({ analysis }: { analysis: AnalyzeResponse }) {
  const dispatch = useAppDispatch()
  const request = useAppSelector((state) => state.trip.request)
  const selectedRouteId = useAppSelector((state) => state.trip.selectedRouteId)

  const best = recommendedRoute(analysis)
  const noSafeRoute = hasNoSafeRoute(analysis)
  const fastestId = fastestRouteId(analysis.routes)
  const activeRouteId = selectedRouteId ?? best?.id
  const fastest = analysis.routes.find((route) => route.id === fastestId)
  const extraTime = best && fastest ? best.metrics.duration_s - fastest.metrics.duration_s : 0

  function departLater() {
    if (!request) return
    const later = new Date(
      new Date(request.departure_time).getTime() + DELAY_SUGGESTION_HOURS * 3_600_000,
    )
    dispatch(analysisSubmitted({ ...request, departure_time: later.toISOString() }))
  }

  return (
    <div className="space-y-3">
      {noSafeRoute ? (
        <StatusAlert
          role="alert"
          tone="purple"
          title="No route is safe at this departure time"
          actions={
            <>
              <Button size="sm" onClick={departLater}>
                Try departing +{DELAY_SUGGESTION_HOURS}h
              </Button>
              <Button size="sm" variant="outline" onClick={() => dispatch(editTrip())}>
                Reduce load
              </Button>
            </>
          }
        >
          Every route crosses No Travel conditions. {best?.label} has the fewest No Travel miles.{' '}
          {analysis.recommendation.reason}
        </StatusAlert>
      ) : (
        best && (
          <StatusAlert
            tone="success"
            title={
              <span className="flex flex-wrap items-center gap-2">
                Recommended: {best.label}
                {extraTime > 0 && (
                  <Badge variant="success" className="font-mono">
                    {formatDurationDelta(extraTime)}
                  </Badge>
                )}
              </span>
            }
          >
            {analysis.recommendation.reason}
          </StatusAlert>
        )
      )}

      {resultNotices(analysis).map((notice) =>
        notice.kind === 'unknown-weather' ? (
          <StatusAlert key={`u-${notice.routeLabel}`} tone="warning">
            Weather unavailable for {Math.round(notice.miles)} mi of {notice.routeLabel} — shown as
            Unknown. Risk may be understated.
          </StatusAlert>
        ) : (
          <StatusAlert key={`f-${notice.routeLabel}`} tone="info">
            {notice.routeLabel} uses a detour waypoint because the router returned fewer than 3
            routes.
          </StatusAlert>
        ),
      )}

      {analysis.forecast_fetched_at && (
        <p className="text-xs text-muted-foreground">
          Forecast as of {formatClock(analysis.forecast_fetched_at)} · updates every 30 min
        </p>
      )}

      <p className="pt-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        Route options ({analysis.routes.length})
      </p>
      <div className="space-y-3">
        {analysis.routes.map((route) => (
          <RouteCard
            key={route.id}
            route={route}
            departureTime={analysis.departure_time}
            selected={route.id === activeRouteId}
            badge={
              route.id === best?.id ? (noSafeRoute ? 'least-risky' : 'recommended') : undefined
            }
            isFastest={route.id === fastestId && route.id !== best?.id}
            onSelect={() => dispatch(routeSelected(route.id))}
          />
        ))}
      </div>
    </div>
  )
}
