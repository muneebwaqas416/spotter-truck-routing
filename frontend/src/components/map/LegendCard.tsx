import { X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { RiskDot } from '@/components/ui/RiskChip'
import { RISK_ORDER, RISK_RULES, RISK_STYLES } from '@/lib/risk'

export function LegendCard({ onClose }: { onClose: () => void }) {
  return (
    <Card size="sm" aria-label="Risk legend" className="w-80 gap-2 bg-white/95 backdrop-blur">
      <CardHeader>
        <CardTitle className="text-xs tracking-wide text-foreground uppercase">
          Risk levels
        </CardTitle>
        <CardAction>
          <Button variant="ghost" size="icon-xs" aria-label="Hide legend" onClick={onClose}>
            <X />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-2">
        <ul className="space-y-1.5">
          {RISK_ORDER.map((level) => (
            <li key={level} className="flex items-center gap-2 text-xs">
              <RiskDot level={level} />
              <span className="w-16 font-medium text-foreground">{RISK_STYLES[level].label}</span>
              <span className="font-mono text-2xs text-muted-foreground">{RISK_RULES[level]}</span>
            </li>
          ))}
        </ul>
        <p className="border-t pt-2 text-2xs text-muted-foreground">
          Loads over 30,000 lb: wind 45–54 mph is No Travel. Over 40,000 lb: 35–44 mph is Severe.
        </p>
      </CardContent>
    </Card>
  )
}
