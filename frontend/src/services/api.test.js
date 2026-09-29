/**
 * api.test.js — unit tests for the api.js fetch wrapper.
 *
 * Uses vitest globals + jsdom. fetch is replaced with vi.fn() so no real
 * network calls are made.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { request, get, post, del } from './api.js'

// ── helpers ──────────────────────────────────────────────────────────────

function makeResponse({ status = 200, body = {}, headers = {} } = {}) {
  const h = new Headers({ 'content-type': 'application/json', ...headers })
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: h,
    text: async () =>
      typeof body === 'string' ? body : JSON.stringify(body),
  }
}

// ── setup ─────────────────────────────────────────────────────────────────

let fetchSpy

beforeEach(() => {
  fetchSpy = vi.fn()
  globalThis.fetch = fetchSpy
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ── request() ─────────────────────────────────────────────────────────────

describe('request()', () => {
  it('returns parsed JSON on 200 ok', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse({ body: { foo: 'bar' } }))
    const result = await request('/test')
    expect(result).toEqual({ foo: 'bar' })
  })

  it('sends Content-Type: application/json by default', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse())
    await request('/test')
    const [, opts] = fetchSpy.mock.calls[0]
    expect(opts.headers['Content-Type']).toBe('application/json')
  })

  it('merges caller headers with Content-Type', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse())
    await request('/test', { headers: { 'X-Custom': 'value' } })
    const [, opts] = fetchSpy.mock.calls[0]
    expect(opts.headers['Content-Type']).toBe('application/json')
    expect(opts.headers['X-Custom']).toBe('value')
  })

  it('throws with detail string on non-ok JSON response', async () => {
    fetchSpy.mockResolvedValueOnce(
      makeResponse({ status: 400, body: { detail: 'title too short' } })
    )
    await expect(request('/test')).rejects.toThrow('title too short')
  })

  it('formats Pydantic validation error array into readable string', async () => {
    fetchSpy.mockResolvedValueOnce(
      makeResponse({
        status: 422,
        body: {
          detail: [
            { loc: ['body', 'title'], msg: 'field required' },
            { loc: ['body', 'severity'], msg: 'value is not a valid enum member' },
          ],
        },
      })
    )
    await expect(request('/test')).rejects.toThrow('title: field required')
  })

  it('falls back to showing short non-JSON body verbatim, or "Server error" for long ones', async () => {
    // Short non-JSON body: shown verbatim (more informative than generic message)
    fetchSpy.mockResolvedValueOnce(
      makeResponse({ status: 503, body: '<html>Bad Gateway</html>' })
    )
    await expect(request('/test')).rejects.toThrow('Bad Gateway')

    // Long non-JSON body: falls back to generic message
    fetchSpy.mockResolvedValueOnce(
      makeResponse({ status: 503, body: 'x'.repeat(400) })
    )
    await expect(request('/test')).rejects.toThrow('Server error (503)')
  })

  it('appends X-Request-ID to error message when present', async () => {
    fetchSpy.mockResolvedValueOnce(
      makeResponse({
        status: 500,
        body: { detail: 'internal error' },
        headers: { 'x-request-id': 'abc-123' },
      })
    )
    await expect(request('/test')).rejects.toThrow('abc-123')
  })

  it('throws timeout error on AbortError', async () => {
    fetchSpy.mockRejectedValueOnce(Object.assign(new Error('abort'), { name: 'AbortError' }))
    await expect(request('/test')).rejects.toThrow(/timed out/)
  })

  it('re-throws non-abort network errors as-is', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('Failed to fetch'))
    await expect(request('/test')).rejects.toThrow('Failed to fetch')
  })

  it('returns null for empty ok response', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse({ body: '' }))
    const result = await request('/test')
    expect(result).toBeNull()
  })

  it('prefixes /api to the path', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse())
    await request('/incidents')
    const [url] = fetchSpy.mock.calls[0]
    expect(url).toMatch('/api/incidents')
  })
})

// ── convenience wrappers ──────────────────────────────────────────────────

describe('get()', () => {
  it('uses GET method', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse())
    await get('/health')
    const [, opts] = fetchSpy.mock.calls[0]
    expect(opts.method).toBe('GET')
  })
})

describe('post()', () => {
  it('uses POST method with serialised body', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse())
    await post('/incidents/analyze', { title: 'test' })
    const [, opts] = fetchSpy.mock.calls[0]
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ title: 'test' })
  })

  it('sends empty object body when called with no data', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse())
    await post('/test')
    const [, opts] = fetchSpy.mock.calls[0]
    expect(JSON.parse(opts.body)).toEqual({})
  })
})

describe('del()', () => {
  it('uses DELETE method', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse())
    await del('/incidents/INC-001')
    const [, opts] = fetchSpy.mock.calls[0]
    expect(opts.method).toBe('DELETE')
  })
})

// ── 401 / 429 surface correctly ───────────────────────────────────────────

describe('error status codes', () => {
  it('surfaces 401 detail', async () => {
    fetchSpy.mockResolvedValueOnce(
      makeResponse({ status: 401, body: { detail: 'Invalid or missing X-API-Key header.' } })
    )
    await expect(request('/incidents')).rejects.toThrow('Invalid or missing X-API-Key')
  })

  it('surfaces 429 detail', async () => {
    fetchSpy.mockResolvedValueOnce(
      makeResponse({
        status: 429,
        body: { detail: 'Rate limit exceeded. Retry after 12 seconds.' },
        headers: { 'retry-after': '12' },
      })
    )
    await expect(request('/incidents/analyze')).rejects.toThrow('Rate limit exceeded')
  })

  it('surfaces 413 detail', async () => {
    fetchSpy.mockResolvedValueOnce(
      makeResponse({ status: 413, body: { detail: 'Request body exceeds the 256 KB limit.' } })
    )
    await expect(request('/incidents/analyze')).rejects.toThrow('256 KB')
  })
})
