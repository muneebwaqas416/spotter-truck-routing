import { ArrowRight, Pencil } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardAction, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime, formatPounds } from '@/lib/format'
import { useAppDispatch } from '@/redux/hooks'
import type { AnalyzeRequest } from '@/redux/types'

import { editTrip } from './tripSlice'

export function TripSummary({ request }: { request: AnalyzeRequest }) {
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
          {formatDateTime(request.departure_time)} · {formatPounds(request.load_lb)} ·{' '}
          {request.interval_mi} mi
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
