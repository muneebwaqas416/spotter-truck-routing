import type { LucideIcon } from 'lucide-react'

/** Leading icon inside a text input; pair the input with `pl-9`. */
export function InputIcon({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <Icon
      aria-hidden
      className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle"
    />
  )
}
