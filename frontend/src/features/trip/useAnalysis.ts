import { skipToken } from '@reduxjs/toolkit/query'

import { useAnalyzeRoutesQuery } from '@/redux/api'
import type { ApiError } from '@/redux/errors'
import { useAppSelector } from '@/redux/hooks'

/**
 * The current analysis, read from the RTK Query cache. Every component that calls
 * this shares one cache entry, so there is exactly one request per unique input.
 */
export function useAnalysis() {
  const request = useAppSelector((state) => state.trip.request)
  const query = useAnalyzeRoutesQuery(request ?? skipToken)
  return {
    request,
    data: query.data,
    error: query.error as ApiError | undefined,
    isLoading: query.isFetching,
    isError: query.isError && !query.isFetching,
    isSuccess: query.isSuccess && !query.isFetching,
    fulfilledAt: query.fulfilledTimeStamp,
    refetch: query.refetch,
  }
}
