import { skipToken } from '@reduxjs/toolkit/query'
import { useMemo } from 'react'

import { useHeatmapQuery } from '@/redux/api'
import type { ApiError } from '@/redux/errors'
import type { AnalyzeResponse, BBox, HeatmapRequest } from '@/redux/types'
import { useAppSelector } from '@/redux/hooks'
import { routesBBox } from '@/features/results/derive'

/** Degrees of padding around the routes so the corridor heatmap has context. */
const CORRIDOR_PADDING_DEG = 0.5

export function heatmapRequestFor(analysis: AnalyzeResponse): HeatmapRequest | undefined {
  const bbox = routesBBox(analysis.routes)
  if (!bbox) return undefined
  const start = new Date(analysis.departure_time)
  start.setUTCMinutes(0, 0, 0)
  return {
    bbox: padBBox(bbox, CORRIDOR_PADDING_DEG),
    start: start.toISOString(),
    load_lb: analysis.load_lb,
  }
}

function padBBox([minLon, minLat, maxLon, maxLat]: BBox, pad: number): BBox {
  const round = (value: number) => Math.round(value * 100) / 100
  return [round(minLon - pad), round(minLat - pad), round(maxLon + pad), round(maxLat + pad)]
}

/** Corridor heatmap for 0–48 h. Fetched once per analysis; the slider never refetches. */
export function useHeatmap(analysis: AnalyzeResponse | undefined) {
  const enabled = useAppSelector((state) => state.trip.heatmapEnabled)
  const args = analysis && enabled ? heatmapRequestFor(analysis) : undefined
  const query = useHeatmapQuery(args ?? skipToken)

  const missingByHour = useMemo(
    () =>
      query.data?.scores.map((hourScores) =>
        hourScores.length === 0
          ? 1
          : hourScores.filter((score) => score === null).length / hourScores.length,
      ) ?? [],
    [query.data],
  )

  return {
    enabled,
    data: query.data,
    isLoading: query.isFetching,
    error: query.isError ? (query.error as ApiError) : undefined,
    refetch: query.refetch,
    missingByHour,
  }
}
