import {
  CircleAlert,
  CircleCheck,
  Info,
  OctagonX,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

export type AlertTone = 'danger' | 'warning' | 'info' | 'purple' | 'success'

const ICONS: Record<AlertTone, LucideIcon> = {
  danger: CircleAlert,
  warning: TriangleAlert,
  info: Info,
  purple: OctagonX,
  success: CircleCheck,
}

interface StatusAlertProps {
  tone: AlertTone
  title?: ReactNode
  children?: ReactNode
  actions?: ReactNode
  icon?: LucideIcon
  role?: 'alert' | 'status'
}

/** shadcn Alert with the app's tone → icon mapping and an optional row of actions. */
export function StatusAlert({
  tone,
  title,
  children,
  actions,
  icon,
  role = 'status',
}: StatusAlertProps) {
  const Icon = icon ?? ICONS[tone]
  return (
    <Alert variant={tone} role={role}>
      <Icon aria-hidden />
      {title && <AlertTitle className="font-semibold">{title}</AlertTitle>}
      {(children || actions) && (
        <AlertDescription>
          {children}
          {actions && <div className="flex flex-wrap items-center gap-2 pt-2">{actions}</div>}
        </AlertDescription>
      )}
    </Alert>
  )
}
