/**
 * Times are always shown with their zone ("19:00 MDT"). Trip times use the trip's own zones
 * (origin for departure and checkpoints, destination for arrival), not the viewer's browser.
 * en-US gives North American abbreviations (MDT, CST) instead of "GMT-6".
 */
const formatters = new Map<string, Intl.DateTimeFormat>()

function formatter(withDate: boolean, timeZone?: string): Intl.DateTimeFormat {
  const key = `${withDate}|${timeZone ?? ''}`
  let cached = formatters.get(key)
  if (!cached) {
    cached = new Intl.DateTimeFormat('en-US', {
      ...(withDate && { month: 'short', day: 'numeric' }),
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
      timeZoneName: 'short',
      timeZone,
    })
    formatters.set(key, cached)
  }
  return cached
}

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

/** "Oct 10, 19:00 MDT" in `timeZone` (IANA name), or the viewer's zone when omitted. */
export function formatDateTime(iso: string, timeZone?: string): string {
  return formatter(true, timeZone).format(new Date(iso))
}

/** "19:00 MDT" in `timeZone` (IANA name), or the viewer's zone when omitted. */
export function formatClock(iso: string, timeZone?: string): string {
  return formatter(false, timeZone).format(new Date(iso))
}

export function formatPounds(pounds: number): string {
  return `${integerFormatter.format(pounds)} lb`
}

export function formatRate(value: number | null, unit: string, digits = 2): string {
  return value === null ? '—' : `${truncate(value, digits)} ${unit}`
}

/**
 * Cuts to `digits` decimals instead of rounding: 34.6 mph shown as "35" would sit next to a
 * Moderate level whose legend says High starts at 35. Trailing zeros are dropped.
 */
export function truncate(value: number, digits: number): string {
  const scale = 10 ** digits
  return String(Math.floor(value * scale + 1e-9) / scale)
}

export function addSeconds(iso: string, seconds: number): string {
  return new Date(new Date(iso).getTime() + seconds * 1000).toISOString()
}
