import { describe, it, expect, beforeEach } from 'vitest'
import { getRequestErrorMessage, hasAccessToken } from './client'

// ── getRequestErrorMessage ──

describe('getRequestErrorMessage', () => {
  it('returns string error directly', () => {
    expect(getRequestErrorMessage('网络异常')).toBe('网络异常')
  })

  it('returns Error.message', () => {
    expect(getRequestErrorMessage(new Error('timeout'))).toBe('timeout')
  })

  it('extracts message from response.data', () => {
    const error = {
      response: { data: { message: '用户不存在' }, status: 400 },
    }
    expect(getRequestErrorMessage(error)).toBe('用户不存在')
  })

  it('extracts detail from response.data', () => {
    const error = {
      response: { data: { detail: '权限不足' }, status: 403 },
    }
    expect(getRequestErrorMessage(error)).toBe('权限不足')
  })

  it('uses displayMessage if present', () => {
    const error = {
      displayMessage: '自定义消息',
      response: { data: {}, status: 500 },
    }
    expect(getRequestErrorMessage(error)).toBe('自定义消息')
  })

  it('returns fallback for null/undefined', () => {
    expect(getRequestErrorMessage(null)).toBe('请求失败')
    expect(getRequestErrorMessage(undefined)).toBe('请求失败')
  })

  it('returns custom fallback', () => {
    expect(getRequestErrorMessage(null, '操作失败')).toBe('操作失败')
  })

  it('returns status message for 404', () => {
    const error = { response: { data: {}, status: 404 } }
    expect(getRequestErrorMessage(error)).toBe('接口不存在')
  })
})

// ── hasAccessToken ──

describe('hasAccessToken', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns false when no token', () => {
    expect(hasAccessToken()).toBe(false)
  })

  it('returns false for invalid token', () => {
    localStorage.setItem('access_token', 'not.a.jwt')
    expect(hasAccessToken()).toBe(false)
  })

  it('returns true for valid non-expired token', () => {
    // Create a JWT with exp far in the future
    const header = btoa(JSON.stringify({ alg: 'HS256' }))
    const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))
    const token = `${header}.${payload}.signature`
    localStorage.setItem('access_token', token)
    expect(hasAccessToken()).toBe(true)
  })

  it('returns false for expired token', () => {
    const header = btoa(JSON.stringify({ alg: 'HS256' }))
    const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) - 100 }))
    const token = `${header}.${payload}.signature`
    localStorage.setItem('access_token', token)
    expect(hasAccessToken()).toBe(false)
  })
})
