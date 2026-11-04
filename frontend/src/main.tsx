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

// The public build only ever uses the demo provider. `?simSpeed=` speeds up playback for automated tests.
const speedParam = Number(new URLSearchParams(window.location.search).get('simSpeed'))
const provider = createDemoProvider({ speed: Number.isFinite(speedParam) && speedParam > 0 ? speedParam : 100 })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders provider={provider}>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
