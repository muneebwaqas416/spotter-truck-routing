import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { RISK_STYLES } from '@/lib/risk'
import type { RiskLevel } from '@/redux/types'

export function RiskDot({ level, className }: { level: RiskLevel; className?: string }) {
  const unknown = level === 'UNKNOWN'
  return (
    <span
      aria-hidden
      className={cn(
        'inline-block size-2.5 shrink-0 rounded-full',
        unknown && 'border border-dashed border-subtle',
        className,
      )}
      style={unknown ? undefined : { backgroundColor: RISK_STYLES[level].color }}
    />
  )
}

/** shadcn Badge tinted with the risk colour. Colours are semantic, so they come from RISK_STYLES. */
export function RiskChip({ level }: { level: RiskLevel }) {
  const style = RISK_STYLES[level]
  const unknown = level === 'UNKNOWN'
  return (
    <Badge
      variant="outline"
      className={cn(unknown && 'text-muted-foreground')}
      style={{
        borderColor: `${style.color}55`,
        backgroundColor: `${style.color}14`,
        color: unknown ? undefined : style.color,
      }}
    >
      <RiskDot level={level} className="size-2" />
      {style.label}
    </Badge>
  )
}
