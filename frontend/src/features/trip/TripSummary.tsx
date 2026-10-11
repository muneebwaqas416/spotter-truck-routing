import { ArrowRight, Pencil } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardAction, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime, formatPounds } from '@/lib/format'
import { useAppDispatch } from '@/redux/hooks'
import type { AnalyzeRequest } from '@/redux/types'

import { editTrip } from './tripSlice'

interface TripSummaryProps {
  request: AnalyzeRequest
  /** Resolved departure (with offset) and origin zone, once the analysis has returned. */
  departure?: string
  timeZone?: string
}

export function TripSummary({ request, departure, timeZone }: TripSummaryProps) {
  const dispatch = useAppDispatch()
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-1.5 text-sm font-semibold">
          <span className="truncate">{request.origin}</span>
          <ArrowRight aria-label="to" className="size-3.5 text-subtle" />
          <span className="truncate">{request.destination}</span>
        </CardTitle>
        <CardDescription className="tabular font-mono text-xs">
          {departure ? formatDateTime(departure, timeZone) : request.departure_time.slice(0, 16)} ·{' '}
          {formatPounds(request.load_lb)} · {request.interval_mi} mi
        </CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" onClick={() => dispatch(editTrip())}>
            <Pencil aria-hidden /> Edit
          </Button>
        </CardAction>
      </CardHeader>
    </Card>
  )
}
