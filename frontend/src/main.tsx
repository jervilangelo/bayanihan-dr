import '@fontsource/dm-sans/400.css'
import '@fontsource/dm-sans/500.css'
import '@fontsource/dm-sans/600.css'
import '@fontsource/dm-sans/700.css'
import './styles.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Link, RouterProvider, createHashRouter } from 'react-router'
import { Shell } from './components/Shell'
import { PageHeader } from './components/ui'
import { createDemoProvider } from './data/demo-provider'
import { createLocalStatusProvider } from './data/local-status-provider'
import { AppProviders } from './lib/context'
import { ActivityPage } from './pages/Activity'
import { BackupsPage } from './pages/Backups'
import { OverviewPage } from './pages/Overview'
import { RecoveryPage } from './pages/Recovery'
import { SettingsPage } from './pages/Settings'

// Hash routing: direct links and refreshes work on GitHub Pages without a server fallback (ADR-006).
const router = createHashRouter([
  {
    element: <Shell />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'backups', element: <BackupsPage /> },
      { path: 'recovery', element: <RecoveryPage /> },
      { path: 'activity', element: <ActivityPage /> },
      { path: 'settings', element: <SettingsPage /> },
      {
        path: '*',
        element: (
          <PageHeader
            title="Page not found"
            subline={
              <>
                That address isn't part of the dashboard. <Link to="/" className="btn btn-text">Go to the overview</Link>
              </>
            }
          />
        ),
      },
    ],
  },
])

// The public (production) build only ever uses the demo provider. Local operations mode exists only on
// the dev server (`npm run dev:ops`), which serves the backup engine's status.json; `import.meta.env.DEV`
// is false in production builds, so the local provider is removed from the GitHub Pages bundle.
// `?simSpeed=` speeds up demo playback for automated tests.
const speedParam = Number(new URLSearchParams(window.location.search).get('simSpeed'))
const provider =
  import.meta.env.DEV && import.meta.env.MODE === 'ops'
    ? createLocalStatusProvider({ url: `${import.meta.env.BASE_URL}__local/status.json` })
    : createDemoProvider({ speed: Number.isFinite(speedParam) && speedParam > 0 ? speedParam : 100 })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders provider={provider}>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
