import { useEffect, useRef } from 'react'
import { toast } from 'sonner'

import { describeError } from '@/features/analysis/describeError'

import type { useHeatmap } from './useHeatmap'

export const HEATMAP_TOAST_ID = 'heatmap'

/** Announces heatmap failures and gaps once per fetch; the map overlay keeps the retry control. */
export function useHeatmapToasts(heatmap: ReturnType<typeof useHeatmap>) {
  const announcedFor = useRef<number | undefined>(undefined)

  useEffect(() => {
    const { startedAt, error, data, missingByHour, isLoading } = heatmap
    if (!heatmap.enabled || isLoading || !startedAt || announcedFor.current === startedAt) return

    if (error) {
      announcedFor.current = startedAt
      const { title, retryable } = describeError(error)
      const fieldReason = error.fieldErrors && Object.values(error.fieldErrors)[0]?.[0]
      toast.error(
        fieldReason
          ? 'Heatmap unavailable for this trip'
          : `Heatmap unavailable — ${title.toLowerCase()}`,
        {
          id: HEATMAP_TOAST_ID,
          description: `${fieldReason ?? error.message} Routes and checkpoint risk are not affected.`,
          duration: 10_000,
          action:
            retryable && !fieldReason
              ? { label: 'Retry', onClick: () => void heatmap.refetch() }
              : undefined,
        },
      )
      return
    }

    if (data) {
      announcedFor.current = startedAt
      const lastHour = missingByHour.length - 1
      const blankFrom = missingByHour.findIndex((missing) => missing === 1)
      if (blankFrom === 0) {
        toast.warning('No heatmap forecast for this departure', {
          id: HEATMAP_TOAST_ID,
          description: 'The departure is near the end of the 14-day forecast window.',
        })
      } else if (blankFrom > 0 && blankFrom <= lastHour) {
        toast.warning(`Heatmap forecast ends at +${blankFrom} h`, {
          id: HEATMAP_TOAST_ID,
          description: 'Later hours are blank: forecasts cover the next 14 days.',
        })
      }
    }
  }, [heatmap])
}
