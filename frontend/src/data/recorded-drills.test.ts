import { describe, expect, it } from 'vitest'
import { LATEST_DRILL, RECORDED_DRILLS } from './recorded-drills'

// Evidence links point at the public GitHub repository (its owner name is public); everything else is checked.
const SERIALIZED = JSON.stringify(RECORDED_DRILLS.map(({ evidence: _evidence, ...rest }) => rest))

describe('recorded drill results (published on the public site)', () => {
  it.each([
    ['AWS account IDs', /\b\d{12}\b/],
    ['IPv4 addresses', /\b\d{1,3}(\.\d{1,3}){3}\b/],
    ['EC2 instance IDs', /\bi-[0-9a-f]{8,17}\b/],
    ['bucket names', /bayanihandr-(backups|tfstate)/],
    ['e-mail addresses', /[^\s@"]+@[^\s@"]+\.[a-z]{2,}/i],
    ['ARNs', /arn:aws/],
    ['S3 version IDs or SSO session names', /sso|VersionId|jervil/i],
  ])('contain no %s', (_, pattern) => {
    expect(SERIALIZED).not.toMatch(pattern)
  })

  it('stage durations add up to the measured RTO', () => {
    for (const d of RECORDED_DRILLS) {
      const sum = d.stages.reduce((s, x) => s + x.seconds, 0)
      expect(Math.abs(sum - d.rtoSeconds)).toBeLessThan(0.5)
    }
  })

  it('match the evidence files', () => {
    expect(LATEST_DRILL.rtoSeconds).toBe(328.9) // phase7-disaster-drill.md
    expect(LATEST_DRILL.rpoSeconds).toBe(26.1)
    expect(RECORDED_DRILLS[1]!.rtoSeconds).toBe(434.9) // phase6-recovery-drill.md
    for (const d of RECORDED_DRILLS) {
      expect(d.rtoSeconds / 60).toBeLessThanOrEqual(d.rtoTargetMinutes)
      expect(d.evidence).toMatch(/^https:\/\/github\.com\/jervilangelo\/bayanihan-dr\/blob\/main\/docs\/evidence\//)
    }
  })
})
