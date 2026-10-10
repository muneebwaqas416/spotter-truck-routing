const timeFormatter = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZoneName: 'short',
})

const clockFormatter = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

const integerFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

export function formatMiles(miles: number): string {
  return `${integerFormatter.format(miles)} mi`
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours === 0) return `${minutes}m`
  return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`
}

/** Signed difference, e.g. "+18 min" or "−5 min". */
export function formatDurationDelta(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  if (minutes === 0) return 'same time'
  const sign = minutes > 0 ? '+' : '−'
  return `${sign}${formatDuration(Math.abs(minutes) * 60).replace(/m$/, ' min')}`
}

export function formatDateTime(iso: string): string {
  return timeFormatter.format(new Date(iso))
}

export function formatClock(iso: string): string {
  return clockFormatter.format(new Date(iso))
}

export function formatPounds(pounds: number): string {
  return `${integerFormatter.format(pounds)} lb`
}

export function formatRate(value: number | null, unit: string, digits = 2): string {
  return value === null ? '—' : `${value.toFixed(digits)} ${unit}`
}

export function addSeconds(iso: string, seconds: number): string {
  return new Date(new Date(iso).getTime() + seconds * 1000).toISOString()
}
