import { describe, expect, it } from 'vitest'
import { RunnerError, createRunnerClient } from './runner-client'

type Call = { url: string; init: RequestInit }

function fakeFetch(status: number, body: unknown, calls: Call[] = []) {
  return (async (url: string, init: RequestInit) => {
    calls.push({ url, init })
    return new Response(JSON.stringify(body), { status })
  }) as unknown as typeof fetch
}

describe('runner client', () => {
  it('sends the token as a bearer header and JSON bodies', async () => {
    const calls: Call[] = []
    const c = createRunnerClient('/r', fakeFetch(202, { id: 'job-1', status: 'preparing' }, calls), () => 'secret')
    await c.startDrill('20261105T055524Z')
    expect(calls[0]!.url).toBe('/r/api/jobs')
    expect((calls[0]!.init.headers as Record<string, string>).Authorization).toBe('Bearer secret')
    expect(JSON.parse(calls[0]!.init.body as string)).toEqual({ type: 'recovery-drill', backup_id: '20261105T055524Z' })
    expect(calls[0]!.url).not.toContain('secret')
  })

  it('refuses to call without a token', async () => {
    const calls: Call[] = []
    const c = createRunnerClient('/r', fakeFetch(200, {}, calls), () => null)
    await expect(c.jobs()).rejects.toMatchObject({ code: 'no-token' })
    expect(calls).toHaveLength(0)
  })

  it('surfaces runner error codes and messages', async () => {
    const c = createRunnerClient('/r', fakeFetch(409, { code: 'job-already-running', detail: 'job x is still restoring' }), () => 't')
    await expect(c.startTeardown()).rejects.toMatchObject({ status: 409, code: 'job-already-running', message: 'job x is still restoring' })
  })

  it('explains an unreachable runner', async () => {
    const down = (async () => {
      throw new TypeError('fetch failed')
    }) as unknown as typeof fetch
    await expect(createRunnerClient('/r', down, () => 't').jobs()).rejects.toBeInstanceOf(RunnerError)
    await expect(createRunnerClient('/r', fakeFetch(502, {}), () => 't').jobs()).rejects.toMatchObject({ code: 'unreachable' })
  })

  it('encodes job IDs in paths', async () => {
    const calls: Call[] = []
    await createRunnerClient('/r', fakeFetch(200, {}, calls), () => 't').job('job/../x')
    expect(calls[0]!.url).toBe('/r/api/jobs/job%2F..%2Fx')
  })
})
