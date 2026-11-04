import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import type { DashboardProvider } from '../data/types'
import type { TimeZonePref } from './format'

const ProviderContext = createContext<DashboardProvider | null>(null)

export function useProvider(): DashboardProvider {
  const p = useContext(ProviderContext)
  if (!p) throw new Error('DashboardProvider missing')
  return p
}

export interface Preferences {
  timeZone: TimeZonePref
  motion: 'system' | 'reduce'
}

const DEFAULT_PREFS: Preferences = { timeZone: 'pht', motion: 'system' }
const PREFS_KEY = 'bayanihandr.preferences'

function loadPrefs(): Preferences {
  try {
    const raw = localStorage.getItem(PREFS_KEY)
    return raw ? { ...DEFAULT_PREFS, ...(JSON.parse(raw) as Partial<Preferences>) } : DEFAULT_PREFS
  } catch {
    return DEFAULT_PREFS
  }
}

const PrefsContext = createContext<{ prefs: Preferences; setPrefs: (p: Partial<Preferences>) => void }>({
  prefs: DEFAULT_PREFS,
  setPrefs: () => {},
})

export function usePrefs() {
  return useContext(PrefsContext)
}

export function AppProviders({ provider, children }: { provider: DashboardProvider; children: ReactNode }) {
  const [prefs, setState] = useState<Preferences>(loadPrefs)

  const setPrefs = useCallback((patch: Partial<Preferences>) => {
    setState((prev) => {
      const next = { ...prev, ...patch }
      try {
        localStorage.setItem(PREFS_KEY, JSON.stringify(next))
      } catch {
        /* storage unavailable (private window): keep the preference for this visit only */
      }
      return next
    })
  }, [])

  useEffect(() => {
    document.documentElement.dataset.motion = prefs.motion
  }, [prefs.motion])

  return (
    <ProviderContext.Provider value={provider}>
      <PrefsContext.Provider value={{ prefs, setPrefs }}>{children}</PrefsContext.Provider>
    </ProviderContext.Provider>
  )
}

export interface Resource<T> {
  data: T | null
  error: Error | null
  loading: boolean
  retry: () => void
}

/** Loads one block's data. Each block owns its loading and error state (no full-screen spinners). */
export function useResource<T>(load: (p: DashboardProvider) => Promise<T>): Resource<T> {
  const provider = useProvider()
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<{ data: T | null; error: Error | null; loading: boolean }>({
    data: null,
    error: null,
    loading: true,
  })

  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true, error: null }))
    load(provider).then(
      (data) => alive && setState({ data, error: null, loading: false }),
      (error: unknown) =>
        alive && setState({ data: null, error: error instanceof Error ? error : new Error(String(error)), loading: false }),
    )
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `load` is a stable module-level selector
  }, [provider, attempt])

  return { ...state, retry: () => setAttempt((n) => n + 1) }
}
