import { Label } from '@/components/ui/label'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import type { CheckpointInterval } from '@/redux/types'

const OPTIONS: CheckpointInterval[] = [10, 25, 50]

interface IntervalControlProps {
  value: CheckpointInterval
  onChange: (value: CheckpointInterval) => void
  disabled?: boolean
}

export function IntervalControl({ value, onChange, disabled }: IntervalControlProps) {
  return (
    <div className="space-y-1.5">
      <Label id="interval-label">Checkpoint interval</Label>
      <ToggleGroup
        type="single"
        variant="outline"
        aria-labelledby="interval-label"
        value={String(value)}
        // Radix emits "" when the active item is clicked again; keep the current value instead.
        onValueChange={(next) => next && onChange(Number(next) as CheckpointInterval)}
        disabled={disabled}
        className="w-full"
      >
        {OPTIONS.map((option) => (
          <ToggleGroupItem
            key={option}
            value={String(option)}
            className="flex-1 font-mono data-[state=on]:bg-white data-[state=on]:font-semibold data-[state=on]:text-primary"
          >
            {option} mi
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <p className="text-xs text-muted-foreground">
        Weather is sampled at your ETA at each checkpoint.
      </p>
    </div>
  )
}
