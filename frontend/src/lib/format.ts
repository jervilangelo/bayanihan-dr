export type TimeZonePref = 'pht' | 'utc'

const ZONES: Record<TimeZonePref, string> = { pht: 'Asia/Manila', utc: 'UTC' }

function parts(iso: string, tz: TimeZonePref, opts: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat('en-GB', { timeZone: ZONES[tz], ...opts }).format(new Date(iso))
}

/** "13:05" */
export function time(iso: string, tz: TimeZonePref = 'pht'): string {
  return parts(iso, tz, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
}

/** "Wed 4 Nov" */
export function day(iso: string, tz: TimeZonePref = 'pht'): string {
  return parts(iso, tz, { weekday: 'short', day: 'numeric', month: 'short' })
}

/** "Wed 4 Nov, 13:05" */
export function dateTime(iso: string, tz: TimeZonePref = 'pht'): string {
  return `${day(iso, tz)}, ${time(iso, tz)}`
}

export function zoneLabel(tz: TimeZonePref): string {
  return tz === 'pht' ? 'PHT' : 'UTC'
}

/** "47 min", "2 h 07 min" */
export function duration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, '0')} min`
}

/** "07:40" from seconds, for a running clock. */
export function clock(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function bytes(n: number | null): string {
  if (n === null) return '—'
  if (n < 1000) return `${n} B`
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)} kB`
  return `${(n / 1_000_000).toFixed(2)} MB`
}

export function count(n: number): string {
  return n.toLocaleString('en-PH')
}

export function shortHash(sha: string | null): string {
  return sha ? `${sha.slice(0, 8)}…` : '—'
}
