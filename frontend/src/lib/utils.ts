import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Conditional classes with Tailwind conflict resolution (later classes win). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
