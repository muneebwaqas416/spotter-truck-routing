import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
} from '@reduxjs/toolkit/query/react'

import { env } from '@/config/env'

import { normalizeApiError, type ApiError } from './errors'
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  GeocodeSuggestion,
  HealthResponse,
  HeatmapRequest,
  HeatmapResponse,
} from './types'

/**
 * How long an unused result stays cached (seconds). Forecasts update hourly, so
 * weather-derived results are kept briefly; place lookups barely change.
 */
export const CACHE_SECONDS = {
  analysis: 10 * 60,
  heatmap: 15 * 60,
  geocode: 60 * 60,
} as const

const REQUEST_TIMEOUT_MS = 45_000

const rawBaseQuery = fetchBaseQuery({ baseUrl: env.apiBaseUrl, timeout: REQUEST_TIMEOUT_MS })

const baseQuery: BaseQueryFn<string | FetchArgs, unknown, ApiError> = async (
  args,
  api,
  extraOptions,
) => {
  const result = await rawBaseQuery(args, api, extraOptions)
  if (!result.error) return result
  return {
    error: normalizeApiError(result.error, result.meta?.response?.headers),
    meta: result.meta,
  }
}

export const api = createApi({
  reducerPath: 'api',
  baseQuery,
  // Results are pure functions of their inputs; never refetch behind the user's back.
  refetchOnFocus: false,
  refetchOnReconnect: false,
  endpoints: (build) => ({
    health: build.query<HealthResponse, void>({
      query: () => '/health',
    }),

    // A query (not a mutation) despite POST: the analysis is a read with no side effects,
    // so identical inputs are served from cache instead of re-hitting the providers.
    analyzeRoutes: build.query<AnalyzeResponse, AnalyzeRequest>({
      query: (body) => ({ url: '/routes/analyze', method: 'POST', body }),
      keepUnusedDataFor: CACHE_SECONDS.analysis,
    }),

    heatmap: build.query<HeatmapResponse, HeatmapRequest>({
      query: ({ bbox, start, load_lb }) => ({
        url: '/heatmap',
        params: { bbox: bbox.join(','), start, load_lb },
      }),
      keepUnusedDataFor: CACHE_SECONDS.heatmap,
    }),

    geocode: build.query<GeocodeSuggestion[], string>({
      query: (q) => ({ url: '/geocode', params: { q } }),
      keepUnusedDataFor: CACHE_SECONDS.geocode,
    }),
  }),
})

export const {
  useHealthQuery,
  useAnalyzeRoutesQuery,
  useLazyAnalyzeRoutesQuery,
  useHeatmapQuery,
  useGeocodeQuery,
} = api
