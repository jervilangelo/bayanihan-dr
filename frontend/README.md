# BayanihanDR dashboard (System C)

The dashboard for BayanihanDR, built with React, Vite, TypeScript, Tailwind CSS, Motion and Lucide. It
answers two questions for a cooperative administrator: **"Are we protected?"** and **"What do we do next?"**

The current build is the **public demo**. Every number on it is synthetic, it runs on a fixed clock
(13:52 Philippine time, 4 Nov 2026), and the recovery on the Recovery page is a client-side simulation.
It makes no network requests and cannot reach AWS or Terraform. The authenticated operations mode
arrives in Phase 6, behind the same `DashboardProvider` interface.

| Page | What it answers |
|---|---|
| Overview | Age of the newest verified recovery point against the 1-hour target, the last 24 hours of recovery points, the backup record by day, the schedule, and recent activity |
| Backups | Hourly history with filters (all / recovery points / problems), plus each backup's manifest (checksum, test restore, record counts) |
| Recovery | Preflight checks, recovery-point choice, plan preview, explicit approval, live progress, and the result (simulated) |
| Activity | Backup, recovery, infrastructure and audit events by day, with a "warnings and errors only" filter |
| Settings | Recovery targets, schedule and verification, environment, and display preferences (time zone, reduced motion) |

## Run

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173/bayanihan-dr/
npm run dev:ops      # local operations mode: real backups from ../backups/status.json (read-only, dev server only)
npm run build        # type-check + production build into dist/
npm run preview      # serve the build at http://localhost:4173/bayanihan-dr/
```

## Test

```powershell
npm test                          # Vitest: data, readiness rules, simulation state machine, provider contract
npx playwright install chromium   # first time only
npm run test:e2e                  # Playwright on the production build, desktop and phone
```

`?simSpeed=<n>` before the `#` speeds up the simulation's playback; the e2e tests use it.

## Structure

```
src/data/        provider contract (types.ts), demo dataset, readiness rules, simulation, demo provider
src/lib/         formatting (PHT/UTC), provider and preference context, block-level data loading
src/components/  shell (sidebar / phone menu), recovery-point strip, UI primitives
src/pages/       the five pages
e2e/             Playwright specs
```

Design decisions: `docs/DECISIONS.md` ADR-006 (hash routing), ADR-007 (design system), ADR-008 (provider and simulation).

## Published results and live-site checks

- `src/data/recorded-drills.ts`: sanitized results of the real AWS drills (Phase 6, Phase 7), shown on the
  Overview as "Measured in real AWS drills". A unit test blocks account IDs, IPs, instance IDs, bucket names,
  e-mails and ARNs, and checks that stage durations add up to each RTO.
- `npm run test:public`: Playwright against the live GitHub Pages site (`e2e-public/`). It also runs after each
  deployment and weekly (`.github/workflows/public-site.yml`).
- `E2E_PORT=4175 npm run test:e2e`: use another port when 4174 is taken.
- `node scripts/screenshots.mjs`: regenerate `docs/screenshots/`.
