/**
 * Types mirroring the Django API contract (see CLAUDE.md §7). The backend is the
 * source of truth for every risk decision; the frontend only renders what it receives.
 */

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'SEVERE' | 'NO_TRAVEL' | 'UNKNOWN'

export type CheckpointInterval = 10 | 25 | 50

/** [longitude, latitude], matching GeoJSON and deck.gl ordering. */
export type LngLat = [number, number]

/** [minLon, minLat, maxLon, maxLat] */
export type BBox = [number, number, number, number]

export interface Place {
  label: string
  position: LngLat
  /** IANA timezone, e.g. "America/Denver". */
  time_zone: string
}

// --- POST /routes/analyze ---------------------------------------------------

export interface AnalyzeRequest {
  origin: string
  destination: string
  /** Wall-clock time at the origin, ISO 8601 without offset ("2026-10-11T06:00:00").
   *  The backend applies the origin's timezone. */
  departure_time: string
  load_lb: number
  interval_mi: CheckpointInterval
}

/** Forecast values at the checkpoint's ETA. Null means the provider had no data. */
export interface WeatherSample {
  forecast_time: string | null
  wind_mph: number | null
  gust_mph: number | null
  rain_in_hr: number | null
  snow_in_hr: number | null
}

export interface Checkpoint {
  index: number
  position: LngLat
  mile: number
  eta: string
  weather: WeatherSample
  risk: RiskLevel
  /** Human-readable drivers of the level, e.g. "Wind 38 mph with load > 40,000 lb". */
  reasons: string[]
}

export interface RouteMetrics {
  distance_mi: number
  duration_s: number
  miles_by_risk: Record<RiskLevel, number>
  /** Distance-weighted over known miles; null when no miles could be evaluated. */
  avg_risk: number | null
}

export interface RouteOption {
  id: string
  label: string
  geometry: LngLat[]
  metrics: RouteMetrics
  checkpoints: Checkpoint[]
  /** True when generated via a detour waypoint because the router returned < 3 routes. */
  is_fallback_alternative: boolean
  /** Why this route ranked below the recommendation; null for the recommended route. */
  ranking_note: string | null
}

export interface Recommendation {
  route_id: string
  reason: string
}

export interface AnalyzeResponse {
  origin: Place
  destination: Place
  departure_time: string
  load_lb: number
  interval_mi: CheckpointInterval
  /** When the oldest weather forecast used was fetched (forecasts are cached up to 30 min). */
  forecast_fetched_at: string | null
  routes: RouteOption[]
  recommendation: Recommendation
}

// --- GET /heatmap -----------------------------------------------------------

export interface HeatmapRequest {
  bbox: BBox
  /** ISO 8601 start of the 0–48 h window. */
  start: string
  /** Same load rules as the route analysis. */
  load_lb: number
}

export interface HeatmapResponse {
  points: LngLat[]
  /** 49 hourly timestamps (0–48 h). */
  hours: string[]
  /** scores[hourIndex][pointIndex]; null where the forecast is unavailable. */
  scores: (number | null)[][]
}

// --- GET /geocode -----------------------------------------------------------

export interface GeocodeSuggestion {
  id: string
  label: string
  position: LngLat
}

export interface HealthResponse {
  status: 'ok'
}
