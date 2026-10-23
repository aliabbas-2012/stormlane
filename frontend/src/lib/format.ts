const timeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

/** "Thu 2:30 PM CDT": browser-local time, always with a zone label. */
export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso))
}

/** "Thu, Oct 23, 2:30 PM CDT" */
export function formatDateTime(iso: string): string {
  return dateTimeFormat.format(new Date(iso))
}

export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return hours ? `${hours} h ${String(mins).padStart(2, '0')} min` : `${mins} min`
}

export function formatMiles(miles: number): string {
  return `${Math.round(miles).toLocaleString()} mi`
}

export function formatLbs(lbs: number): string {
  return `${Math.round(lbs).toLocaleString()} lb`
}

/** Value for <input type="datetime-local"> in the browser's zone. */
export function toDateTimeLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** datetime-local values have no zone; the browser's zone is meant, so send an explicit
 * UTC instant rather than a naive string the backend would reject. */
export function dateTimeLocalToIso(value: string): string {
  return new Date(value).toISOString()
}

export function defaultDeparture(): string {
  const date = new Date(Date.now() + 60 * 60 * 1000)
  date.setMinutes(Math.ceil(date.getMinutes() / 15) * 15, 0, 0)
  return toDateTimeLocalValue(date)
}
