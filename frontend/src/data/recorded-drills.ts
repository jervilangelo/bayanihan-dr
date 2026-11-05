/**
 * Results recorded from REAL recovery drills in AWS (not simulated), published on the public site (blueprint Phase 9).
 *
 * Sanitized: no account IDs, bucket names, instance IDs, IP addresses or e-mail addresses. Every number comes from
 * the evidence files in docs/evidence/, and stage durations add up to the measured RTO. A unit test enforces both.
 */

export interface DrillStage {
  label: string
  seconds: number
}

export interface RecordedDrill {
  id: string
  title: string
  date: string // UTC, ISO
  kind: 'disaster drill' | 'controlled drill'
  rtoSeconds: number
  rpoSeconds: number
  rtoTargetMinutes: number
  rpoTargetMinutes: number
  verification: string
  records: { farmers: number; inventoryItems: number; transactions: number }
  stages: DrillStage[]
  costUsd: number
  criteria?: string
  note: string
  evidence: string
}

const EVIDENCE = 'https://github.com/jervilangelo/bayanihan-dr/blob/main/docs/evidence'

export const RECORDED_DRILLS: RecordedDrill[] = [
  {
    id: 'phase7-disaster-drill',
    title: 'Disaster drill: office server down',
    date: '2026-11-05T06:32:16.901Z',
    kind: 'disaster drill',
    rtoSeconds: 328.9,
    rpoSeconds: 26.1,
    rtoTargetMinutes: 30,
    rpoTargetMinutes: 60,
    verification: 'Independent check from the operator workstation (SSM tunnel)',
    records: { farmers: 1051, inventoryItems: 26, transactions: 3001 },
    stages: [
      { label: 'Checks and plan', seconds: 28.0 },
      { label: 'Approval', seconds: 0.9 },
      { label: 'Provision (Terraform)', seconds: 29.7 },
      { label: 'Host setup', seconds: 112.4 },
      { label: 'Download and checksum', seconds: 14.1 },
      { label: 'Database start and restore', seconds: 61.2 },
      { label: 'CMS start and health', seconds: 67.3 },
      { label: 'Verification', seconds: 15.3 },
    ],
    costUsd: 0.0036,
    criteria: '10 of 10 pass criteria met',
    note:
      'Primary stopped, recovered from a fresh clone of the repository. A record written before the backup survived; one written after it was lost, as the RPO predicts. A corrupted off-site backup was refused at the checksum in the same exercise. The 26-second RPO reflects a backup taken just before the outage; with hourly backups the worst case is close to an hour.',
    evidence: `${EVIDENCE}/phase7-disaster-drill.md`,
  },
  {
    id: 'phase6-first-drill',
    title: 'First controlled recovery drill',
    date: '2026-11-05T06:15:02.999Z',
    kind: 'controlled drill',
    rtoSeconds: 434.9,
    rpoSeconds: 1178.3,
    rtoTargetMinutes: 30,
    rpoTargetMinutes: 60,
    verification: 'Reported by the recovery host',
    records: { farmers: 1050, inventoryItems: 26, transactions: 3001 },
    stages: [
      { label: 'Checks and plan', seconds: 34.0 },
      { label: 'Approval', seconds: 128.6 },
      { label: 'Provision (Terraform)', seconds: 31.9 },
      { label: 'Host setup', seconds: 94.5 },
      { label: 'Download and checksum', seconds: 14.0 },
      { label: 'Database start and restore', seconds: 61.0 },
      { label: 'CMS start and health', seconds: 68.0 },
      { label: 'Verification', seconds: 2.9 },
    ],
    costUsd: 0.004,
    note: 'Primary still running. RTO includes 2 min 9 s waiting for the operator to approve the plan, as it would in a real incident.',
    evidence: `${EVIDENCE}/phase6-recovery-drill.md`,
  },
]

export const LATEST_DRILL: RecordedDrill = RECORDED_DRILLS[0]!
