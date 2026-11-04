import { Archive, Gauge, LifeBuoy, ListChecks, Menu, Settings2, X, type LucideIcon } from 'lucide-react'
import { AnimatePresence, MotionConfig, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { useProvider, usePrefs } from '../lib/context'
import { Mark } from './Mark'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

export const NAV: NavItem[] = [
  { to: '/', label: 'Overview', icon: Gauge },
  { to: '/backups', label: 'Backups', icon: Archive },
  { to: '/recovery', label: 'Recovery', icon: LifeBuoy },
  { to: '/activity', label: 'Activity', icon: ListChecks },
  { to: '/settings', label: 'Settings', icon: Settings2 },
]

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <ul className="flex flex-col gap-0.5">
      {NAV.map(({ to, label, icon: Icon }) => (
        <li key={to}>
          <NavLink
            to={to}
            end={to === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              `group flex h-11 items-center gap-2.5 rounded-lg px-3 text-[14px] transition-colors duration-150 lg:h-9 ${
                isActive ? 'bg-tint font-medium text-accent-ink' : 'text-muted hover:bg-raised hover:text-ink'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={16} strokeWidth={1.75} className={isActive ? 'text-accent' : 'text-muted group-hover:text-ink'} aria-hidden="true" />
                {label}
              </>
            )}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <Mark />
      <div className="leading-tight">
        <div className="text-[15px] font-bold tracking-[-0.01em] text-ink">BayanihanDR</div>
        <div className="text-[12px] text-muted">Bicol Farmers Cooperative</div>
      </div>
    </div>
  )
}

function ModeNote() {
  const provider = useProvider()
  return provider.mode === 'demo' ? (
    <div className="rounded-lg border border-warn-border bg-warn-bg px-3 py-2.5 text-[12px] leading-[18px] text-warn-ink">
      <span className="font-semibold">Demo mode.</span> Simulated data on a fixed clock. Nothing here connects to AWS.
    </div>
  ) : (
    <div className="rounded-lg border border-rule bg-sky-tint px-3 py-2.5 text-[12px] leading-[18px] text-sky-ink">
      <span className="font-semibold">Local operations, read-only.</span> Real backups from this computer. Nothing here connects to AWS.
    </div>
  )
}

export function Shell() {
  const location = useLocation()
  const { prefs } = usePrefs()
  const provider = useProvider()
  const [menuOpen, setMenuOpen] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const current = NAV.find((n) => (n.to === '/' ? location.pathname === '/' : location.pathname.startsWith(n.to)))

  useEffect(() => {
    const d = dialogRef.current
    if (!d) return
    if (menuOpen && !d.open) d.showModal()
    if (!menuOpen && d.open) d.close()
  }, [menuOpen])

  useEffect(() => {
    document.title = current ? `${current.label} · BayanihanDR` : 'BayanihanDR'
  }, [current])

  return (
    <MotionConfig reducedMotion={prefs.motion === 'reduce' ? 'always' : 'user'}>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <div className="min-h-dvh lg:grid lg:grid-cols-[240px_1fr]">
        {/* desktop sidebar: on the page ground, no chrome */}
        <aside className="sticky top-0 hidden h-dvh flex-col gap-8 px-3 py-6 lg:flex" aria-label="Main">
          <div className="px-3">
            <Brand />
          </div>
          <nav aria-label="Pages">
            <NavList />
          </nav>
          <div className="mt-auto flex flex-col gap-3">
            <ModeNote />
            <div className="px-3 text-[12px] leading-[18px] text-muted">
              Recovery region <span className="text-ink">Singapore</span>
              <br />
              Times in <span className="text-ink">{prefs.timeZone === 'pht' ? 'Philippine time' : 'UTC'}</span>
            </div>
          </div>
        </aside>

        {/* phone and tablet top bar */}
        <div className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-ground px-5 lg:hidden">
          <div className="flex items-center gap-2.5">
            <Mark size={26} />
            <span className="text-[15px] font-semibold text-ink">{current?.label ?? 'BayanihanDR'}</span>
          </div>
          <button type="button" className="btn btn-secondary h-11 w-11 px-0" aria-label="Open menu" onClick={() => setMenuOpen(true)}>
            <Menu size={18} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        <dialog
          ref={dialogRef}
          aria-label="Menu"
          onClose={() => setMenuOpen(false)}
          className="m-0 h-dvh max-h-none w-full max-w-none bg-ground p-0 backdrop:bg-ink/20 lg:hidden"
        >
          <div className="flex h-full flex-col gap-6 px-4 pt-3 pb-6">
            <div className="flex h-11 items-center justify-between">
              <Brand />
              <button type="button" className="btn btn-secondary h-11 w-11 px-0" aria-label="Close menu" onClick={() => setMenuOpen(false)}>
                <X size={18} strokeWidth={1.75} aria-hidden="true" />
              </button>
            </div>
            <nav aria-label="Pages">
              <NavList onNavigate={() => setMenuOpen(false)} />
            </nav>
            <div className="mt-auto">
              <ModeNote />
            </div>
          </div>
        </dialog>

        <main id="main" className="min-w-0 px-5 pt-5 pb-16 sm:px-6 lg:px-10 lg:pt-8">
          {provider.mode === 'demo' && (
            <p className="mb-6 rounded-lg border border-warn-border bg-warn-bg px-4 py-2.5 text-[13px] leading-5 text-warn-ink lg:hidden">
              Demo mode: simulated data. Nothing here connects to AWS.
            </p>
          )}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, transition: { duration: 0.12 } }}
              transition={{ duration: 0.2, ease: [0.2, 0, 0, 1] }}
              className="mx-auto max-w-[1240px]"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </MotionConfig>
  )
}
