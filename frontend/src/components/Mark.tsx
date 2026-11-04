/**
 * The BayanihanDR mark: a nipa hut raised on the shoulder pole that neighbours carry it with in
 * the bayanihan tradition. The community moving the house to safety is what recovery means here.
 */
export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="8" fill="var(--color-tint)" />
      <path d="M8 15.5 16 8.5l8 7z" fill="var(--color-accent)" />
      <rect x="10.5" y="15.5" width="11" height="6.5" fill="var(--color-accent)" />
      <rect x="14.5" y="18" width="3" height="4" fill="var(--color-tint)" />
      <rect x="5" y="23.5" width="22" height="2" rx="1" fill="var(--color-ink)" />
    </svg>
  )
}
