/** Helpers between <input type="datetime-local"> values and timezone-aware ISO strings. */

const pad = (n: number) => String(n).padStart(2, '0')

/** "YYYY-MM-DDTHH:mm" in the browser's local time zone. */
export function toLocalInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

/** Local input value → ISO 8601 with the local UTC offset, e.g. 2026-10-10T06:00:00-06:00. */
export function localInputToIso(value: string): string {
  const date = new Date(value)
  const offsetMinutes = -date.getTimezoneOffset()
  const sign = offsetMinutes >= 0 ? '+' : '-'
  const abs = Math.abs(offsetMinutes)
  return `${toLocalInputValue(date)}:00${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
}

/** Next full hour from now: a sensible default departure. */
export function nextFullHour(now = new Date()): Date {
  const next = new Date(now)
  next.setMinutes(0, 0, 0)
  next.setHours(next.getHours() + 1)
  return next
}

export function addHours(date: Date, hours: number): Date {
  return new Date(date.getTime() + hours * 3_600_000)
}
