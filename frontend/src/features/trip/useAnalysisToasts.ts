import { useEffect, useRef } from 'react'
import { toast } from 'sonner'

import { describeError } from '@/features/analysis/describeError'
import { HEATMAP_TOAST_ID } from '@/features/heatmap/useHeatmapToasts'
import { hasNoSafeRoute, recommendedRoute, resultNotices } from '@/features/results/derive'
import type { ApiError } from '@/redux/errors'
import type { AnalyzeResponse } from '@/redux/types'
import { useAppSelector } from '@/redux/hooks'

import { useAnalysis } from './useAnalysis'

const TOAST_ID = 'analysis'
/** Long enough to read the explanation before it disappears. */
const WARNING_DURATION_MS = 10_000

/**
 * Toasts only what needs attention: failures and warnings a driver must not miss. A normal
 * recommendation is already in the side panel, so it gets no toast.
 */
export function useAnalysisToasts() {
  const submittedAt = useAppSelector((state) => state.trip.submittedAt)
  const analysis = useAnalysis()
  const announcedFor = useRef<number | null>(null)

  // A new trip makes the previous trip's toasts stale. Updating a toast by id keeps its old place
  // in the stack, so clear them and let this trip's outcome appear on top.
  useEffect(() => {
    if (!submittedAt) return
    toast.dismiss(TOAST_ID)
    toast.dismiss(HEATMAP_TOAST_ID)
  }, [submittedAt])

  useEffect(() => {
    if (!submittedAt || announcedFor.current === submittedAt) return
    if (analysis.isSuccess && analysis.data) {
      announcedFor.current = submittedAt
      warnAboutResult(analysis.data)
    } else if (analysis.isError && analysis.error) {
      announcedFor.current = submittedAt
      announceError(analysis.error, () => void analysis.refetch())
    }
  }, [submittedAt, analysis])
}

/** Warns when no route is drivable or when missing weather may understate the risk. */
function warnAboutResult(data: AnalyzeResponse) {
  const gaps = resultNotices(data).flatMap((notice) =>
    notice.kind === 'unknown-weather'
      ? [`${Math.round(notice.miles)} mi of ${notice.routeLabel}`]
      : [],
  )
  const gapsText =
    gaps.length > 0
      ? `Weather is unavailable for ${gaps.join(', ')}; risk there may be understated.`
      : ''

  if (hasNoSafeRoute(data)) {
    toast.warning(
      `No route is safe at this departure. Least risky: ${recommendedRoute(data)?.label}`,
      {
        id: TOAST_ID,
        description:
          `Every route crosses No Travel conditions. Try a later departure or a lighter load. ${gapsText}`.trim(),
        duration: WARNING_DURATION_MS,
      },
    )
  } else if (gaps.length > 0) {
    toast.warning('Some of the forecast is missing', {
      id: TOAST_ID,
      description: `${gapsText} These miles are shown as Unknown.`,
      duration: WARNING_DURATION_MS,
    })
  }
}

function announceError(error: ApiError, retry: () => void) {
  const { title, body, retryable } = describeError(error)
  toast.error(`Analysis failed — ${title.toLowerCase()}`, {
    id: TOAST_ID,
    description: body,
    duration: WARNING_DURATION_MS,
    action: retryable ? { label: 'Retry', onClick: retry } : undefined,
  })
}
