import { useEffect, useRef } from 'react'
import { toast } from 'sonner'

import { describeError } from '@/features/analysis/describeError'
import { useAppSelector } from '@/redux/hooks'

import { useAnalysis } from './useAnalysis'

/** Announces analysis outcomes once per submission, including when served from cache. */
export function useAnalysisToasts() {
  const submittedAt = useAppSelector((state) => state.trip.submittedAt)
  const analysis = useAnalysis()
  const announcedFor = useRef<number | null>(null)

  useEffect(() => {
    if (!submittedAt || announcedFor.current === submittedAt) return
    if (analysis.isSuccess && analysis.data) {
      announcedFor.current = submittedAt
      const cachedMinutes =
        analysis.fulfilledAt && analysis.fulfilledAt < submittedAt
          ? Math.max(1, Math.round((submittedAt - analysis.fulfilledAt) / 60_000))
          : null
      if (cachedMinutes === null) {
        toast.success(`Analysis complete · ${analysis.data.routes.length} routes`)
      } else {
        toast.info(`Showing results from ${cachedMinutes} min ago`, {
          action: { label: 'Refresh', onClick: () => void analysis.refetch() },
        })
      }
    } else if (analysis.isError && analysis.error) {
      announcedFor.current = submittedAt
      const { title, retryable } = describeError(analysis.error)
      toast.error(`Analysis failed — ${title.toLowerCase()}`, {
        action: retryable ? { label: 'Retry', onClick: () => void analysis.refetch() } : undefined,
      })
    }
  }, [submittedAt, analysis])
}
