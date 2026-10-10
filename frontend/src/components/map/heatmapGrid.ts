import type { BBox, LngLat } from '@/redux/types'
import { HEATMAP_COLOR_RANGE } from '@/lib/risk'

export interface GridImage {
  width: number
  height: number
  /** RGBA pixels, row 0 = northernmost row (image orientation). */
  data: Uint8ClampedArray<ArrayBuffer>
  /** Image edges in lon/lat, extended half a cell beyond the outer sample centres. */
  bounds: BBox
}

const MAX_SCORE = 4
/** Low risk is a light tint (still visibly 'on'); danger is near-opaque. */
const MIN_ALPHA = 64
const MAX_ALPHA = 190

/**
 * Rasterises a regular forecast grid (one sample per point) into a small RGBA image.
 * Missing samples become fully transparent so unknown areas never read as safe.
 */
export function gridToImage(points: LngLat[], scores: (number | null)[]): GridImage | undefined {
  const lons = uniqueSorted(points.map(([lon]) => key(lon)))
  const lats = uniqueSorted(points.map(([, lat]) => key(lat)))
  if (lons.length < 2 || lats.length < 2) return undefined

  const width = lons.length
  const height = lats.length
  const colIndex = new Map(lons.map((lon, i) => [lon, i]))
  const rowIndex = new Map(lats.map((lat, i) => [lat, height - 1 - i]))
  const data = new Uint8ClampedArray(width * height * 4)

  points.forEach(([lon, lat], i) => {
    const score = scores[i]
    const col = colIndex.get(key(lon))
    const row = rowIndex.get(key(lat))
    if (score === null || score === undefined || col === undefined || row === undefined) return
    const [r, g, b] = rampColor(score)
    const offset = (row * width + col) * 4
    data[offset] = r
    data[offset + 1] = g
    data[offset + 2] = b
    data[offset + 3] = MIN_ALPHA + ((MAX_ALPHA - MIN_ALPHA) * clamp(score)) / MAX_SCORE
  })

  const halfLon = ((lons[width - 1] as number) - (lons[0] as number)) / (width - 1) / 2
  const halfLat = ((lats[height - 1] as number) - (lats[0] as number)) / (height - 1) / 2
  return {
    width,
    height,
    data,
    bounds: [
      (lons[0] as number) - halfLon,
      (lats[0] as number) - halfLat,
      (lons[width - 1] as number) + halfLon,
      (lats[height - 1] as number) + halfLat,
    ],
  }
}

function clamp(score: number): number {
  return Math.min(MAX_SCORE, Math.max(0, score))
}

/** Linear interpolation across the risk palette for fractional scores. */
export function rampColor(score: number): [number, number, number] {
  const position = clamp(score)
  const lower = Math.floor(position)
  const upper = Math.min(MAX_SCORE, lower + 1)
  const t = position - lower
  const a = HEATMAP_COLOR_RANGE[lower] as [number, number, number]
  const b = HEATMAP_COLOR_RANGE[upper] as [number, number, number]
  return [0, 1, 2].map((i) =>
    Math.round((a[i] as number) + ((b[i] as number) - (a[i] as number)) * t),
  ) as [number, number, number]
}

/** Coordinates from arithmetic grids carry float noise; compare them at micro-degree precision. */
function key(value: number): number {
  return Math.round(value * 1e6) / 1e6
}

function uniqueSorted(values: number[]): number[] {
  return [...new Set(values)].sort((a, b) => a - b)
}
