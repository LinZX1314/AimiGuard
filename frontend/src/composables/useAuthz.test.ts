import { describe, it, expect, beforeEach } from 'vitest'
import { parseStoredUserInfo, getStoredPermissions, hasPermission, hasAnyPermission } from './useAuthz'

describe('parseStoredUserInfo', () => {
  beforeEach(() => localStorage.clear())

  it('returns null when no user_info', () => {
    expect(parseStoredUserInfo()).toBeNull()
  })

  it('returns null for invalid JSON', () => {
    localStorage.setItem('user_info', 'not json')
    expect(parseStoredUserInfo()).toBeNull()
  })

  it('parses valid user info', () => {
    localStorage.setItem('user_info', JSON.stringify({
      username: 'admin',
      role: 'admin',
      permissions: ['view_system_mode', 'set_system_mode'],
    }))
    const info = parseStoredUserInfo()
    expect(info?.username).toBe('admin')
    expect(info?.role).toBe('admin')
    expect(info?.permissions).toEqual(['view_system_mode', 'set_system_mode'])
  })

  it('handles missing fields gracefully', () => {
    localStorage.setItem('user_info', JSON.stringify({}))
    const info = parseStoredUserInfo()
    expect(info?.username).toBeUndefined()
    expect(info?.role).toBeUndefined()
    expect(info?.permissions).toEqual([])
  })
})

describe('getStoredPermissions', () => {
  beforeEach(() => localStorage.clear())

  it('returns empty array when no user', () => {
    expect(getStoredPermissions()).toEqual([])
  })

  it('returns permissions from stored user', () => {
    localStorage.setItem('user_info', JSON.stringify({
      permissions: ['p1', 'p2'],
    }))
    expect(getStoredPermissions()).toEqual(['p1', 'p2'])
  })
})

describe('hasPermission', () => {
  beforeEach(() => localStorage.clear())

  it('returns false when no user', () => {
    expect(hasPermission('view_system_mode')).toBe(false)
  })

  it('returns true for admin role regardless', () => {
    localStorage.setItem('user_info', JSON.stringify({
      role: 'admin',
      permissions: [],
    }))
    expect(hasPermission('any_permission')).toBe(true)
  })

  it('returns true for operator with workflow_view', () => {
    localStorage.setItem('user_info', JSON.stringify({
      role: 'operator',
      permissions: [],
    }))
    expect(hasPermission('workflow_view')).toBe(true)
  })

  it('returns false for operator without matching permission', () => {
    localStorage.setItem('user_info', JSON.stringify({
      role: 'operator',
      permissions: [],
    }))
    expect(hasPermission('delete_users')).toBe(false)
  })

  it('returns true when permission is in list', () => {
    localStorage.setItem('user_info', JSON.stringify({
      role: 'viewer',
      permissions: ['view_reports'],
    }))
    expect(hasPermission('view_reports')).toBe(true)
  })
})

describe('hasAnyPermission', () => {
  beforeEach(() => localStorage.clear())

  it('returns false when no permissions match', () => {
    localStorage.setItem('user_info', JSON.stringify({
      role: 'viewer',
      permissions: [],
    }))
    expect(hasAnyPermission(['p1', 'p2'])).toBe(false)
  })

  it('returns true when at least one matches', () => {
    localStorage.setItem('user_info', JSON.stringify({
      role: 'viewer',
      permissions: ['p2'],
    }))
    expect(hasAnyPermission(['p1', 'p2'])).toBe(true)
  })
})
