import type { AnalyzeResponse, BBox, RiskLevel, RouteOption } from '@/redux/types'

/** Pure view helpers over the API response; no risk decisions are made here. */

export function milesAt(route: RouteOption, level: RiskLevel): number {
  return route.metrics.miles_by_risk[level] ?? 0
}

export function recommendedRoute(analysis: AnalyzeResponse): RouteOption | undefined {
  return analysis.routes.find((route) => route.id === analysis.recommendation.route_id)
}

export function fastestRouteId(routes: RouteOption[]): string | undefined {
  return [...routes].sort((a, b) => a.metrics.duration_s - b.metrics.duration_s)[0]?.id
}

/** True when even the best-ranked route crosses No Travel conditions. */
export function hasNoSafeRoute(analysis: AnalyzeResponse): boolean {
  const best = recommendedRoute(analysis)
  return best !== undefined && milesAt(best, 'NO_TRAVEL') > 0
}

export type Notice =
  | { kind: 'unknown-weather'; routeLabel: string; miles: number }
  | { kind: 'detours'; providerRoutes: number; detours: { label: string; extraPct: number }[] }

export function resultNotices(analysis: AnalyzeResponse): Notice[] {
  const notices: Notice[] = []
  for (const route of analysis.routes) {
    const unknown = milesAt(route, 'UNKNOWN')
    if (unknown > 0)
      notices.push({ kind: 'unknown-weather', routeLabel: route.label, miles: unknown })
  }
  const detours = analysis.routes.filter((route) => route.is_fallback_alternative)
  if (detours.length > 0) {
    notices.push({
      kind: 'detours',
      providerRoutes: analysis.routes.length - detours.length,
      detours: detours.map((route) => ({
        label: route.label,
        extraPct: detourExtraPct(route, analysis.routes) ?? 0,
      })),
    })
  }
  return notices
}

/** How much longer a generated detour is than the shortest provider route, in percent. */
export function detourExtraPct(route: RouteOption, routes: RouteOption[]): number | undefined {
  if (!route.is_fallback_alternative) return undefined
  const provider = routes.filter((r) => !r.is_fallback_alternative)
  const shortest = Math.min(...provider.map((r) => r.metrics.distance_mi))
  if (!Number.isFinite(shortest) || shortest <= 0) return undefined
  return Math.round((route.metrics.distance_mi / shortest - 1) * 100)
}

export function routesBBox(routes: RouteOption[]): BBox | undefined {
  const coords = routes.flatMap((route) => route.geometry)
  if (coords.length === 0) return undefined
  let [minLon, minLat, maxLon, maxLat] = [Infinity, Infinity, -Infinity, -Infinity]
  for (const [lon, lat] of coords) {
    minLon = Math.min(minLon, lon)
    minLat = Math.min(minLat, lat)
    maxLon = Math.max(maxLon, lon)
    maxLat = Math.max(maxLat, lat)
  }
  return [minLon, minLat, maxLon, maxLat]
}
