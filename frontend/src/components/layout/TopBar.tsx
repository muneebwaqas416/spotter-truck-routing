import { Layers, Truck } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { legendToggled } from '@/features/trip/tripSlice'
import { useAppDispatch, useAppSelector } from '@/redux/hooks'

export function TopBar() {
  const dispatch = useAppDispatch()
  const legendOpen = useAppSelector((state) => state.trip.legendOpen)
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b bg-white px-4">
      <div className="flex items-center gap-2">
        <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-white">
          <Truck aria-hidden className="size-4" />
        </span>
        <span className="text-lg font-bold tracking-tight text-foreground">
          Truck Route Weather
        </span>
      </div>
      <Button variant="outline" aria-pressed={legendOpen} onClick={() => dispatch(legendToggled())}>
        <Layers aria-hidden /> Legend
      </Button>
    </header>
  )
}
