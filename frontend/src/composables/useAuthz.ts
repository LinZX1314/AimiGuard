export interface StoredUserInfo {
  username?: string
  role?: string
  permissions?: string[]
}

export const parseStoredUserInfo = (): StoredUserInfo | null => {
  const raw = localStorage.getItem('user_info')
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as StoredUserInfo
    return {
      username: typeof value?.username === 'string' ? value.username : undefined,
      role: typeof value?.role === 'string' ? value.role : undefined,
      permissions: Array.isArray(value?.permissions) ? value.permissions.map((item) => String(item)) : [],
    }
  } catch {
    return null
  }
}

export const getStoredPermissions = (): string[] => {
  return parseStoredUserInfo()?.permissions ?? []
}

export const hasPermission = (permission: string): boolean => {
  const user = parseStoredUserInfo()
  const permissions = user?.permissions ?? []
  if (permissions.includes(permission)) return true
  if ((user?.role ?? 'viewer') === 'admin') return true
  if ((user?.role ?? 'viewer') === 'operator' && permission === 'workflow_view') return true
  return false
}

export const hasAnyPermission = (permissions: string[]): boolean => {
  return permissions.some((item) => hasPermission(item))
}
