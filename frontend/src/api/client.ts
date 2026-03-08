import axios from 'axios'
import { toast } from 'vue-sonner'

const DEFAULT_REQUEST_ERROR = '请求失败'
const DEFAULT_UNAUTHORIZED_MESSAGE = '登录状态已失效，请重新登录'

const stripTrailingSlash = (value: string): string => value.replace(/\/+$/, '')

const resolveApiHostRoot = (value: string): string => {
  const normalized = stripTrailingSlash(value)
  if (normalized.endsWith('/api/v1')) return normalized.slice(0, -'/api/v1'.length)
  if (normalized.endsWith('/api')) return normalized.slice(0, -'/api'.length)
  return normalized
}

const resolveApiBaseUrl = (value: string): string => {
  const normalized = stripTrailingSlash(value)
  if (normalized.endsWith('/api/v1')) return normalized
  if (normalized.endsWith('/api')) return `${normalized}/v1`
  return `${normalized}/api/v1`
}

const rawApiBaseUrl = typeof import.meta.env.VITE_API_BASE_URL === 'string'
  ? import.meta.env.VITE_API_BASE_URL.trim()
  : ''

const apiHostRoot = rawApiBaseUrl ? resolveApiHostRoot(rawApiBaseUrl) : ''
const apiBaseUrl = rawApiBaseUrl ? resolveApiBaseUrl(rawApiBaseUrl) : '/api/v1'

let isHandlingUnauthorized = false

const extractMessage = (value: unknown): string | null => {
  if (typeof value === 'string' && value.trim()) {
    return value
  }

  if (!value || typeof value !== 'object') {
    return null
  }

  const record = value as Record<string, unknown>
  const message = record.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }

  const detail = record.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  if (detail && typeof detail === 'object') {
    const detailRecord = detail as Record<string, unknown>
    const nestedMessage = detailRecord.message
    if (typeof nestedMessage === 'string' && nestedMessage.trim()) {
      return nestedMessage
    }
  }

  return null
}

const getStatusMessage = (status: number | undefined): string | null => {
  if (status === 401) return DEFAULT_UNAUTHORIZED_MESSAGE
  if (status === 404) return '接口不存在'
  return null
}

export const getRequestErrorMessage = (error: unknown, fallback = DEFAULT_REQUEST_ERROR): string => {
  if (typeof error === 'string' && error.trim()) {
    return error
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message
  }

  if (!error || typeof error !== 'object') {
    return fallback
  }

  const record = error as Record<string, any>
  const responseData = record.response?.data
  return record.displayMessage || extractMessage(responseData) || getStatusMessage(record.response?.status) || fallback
}

const parseJwtExpiryMs = (token: string): number | null => {
  const parts = token.split('.')
  if (parts.length < 2) return null

  try {
    const payloadBase64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const normalized = payloadBase64.padEnd(payloadBase64.length + ((4 - payloadBase64.length % 4) % 4), '=')
    const payloadText = window.atob(normalized)
    const payload = JSON.parse(payloadText) as { exp?: unknown }
    if (typeof payload.exp !== 'number' || !Number.isFinite(payload.exp)) return null
    return payload.exp * 1000
  } catch {
    return null
  }
}

export const hasAccessToken = (): boolean => {
  try {
    const token = window.localStorage.getItem('access_token')
    if (!token) return false

    const expiryMs = parseJwtExpiryMs(token)
    if (!expiryMs) {
      window.localStorage.removeItem('access_token')
      window.localStorage.removeItem('user_info')
      return false
    }

    if (Date.now() >= expiryMs) {
      window.localStorage.removeItem('access_token')
      window.localStorage.removeItem('user_info')
      return false
    }

    return true
  } catch {
    return false
  }
}

export const buildApiUrl = (path: string): string => (apiHostRoot ? `${apiHostRoot}${path}` : path)

const apiClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    const data = response.data
    // If wrapped in {code, message, data} format, unwrap
    if (data && typeof data === 'object' && 'code' in data && 'data' in data) {
      if (data.code !== 0) {
        return Promise.reject({ response: { data, status: response.status } })
      }
      return data.data
    }
    // Direct response (e.g. login returns TokenResponse directly)
    return data
  },
  (error) => {
    const responseData = error.response?.data
    const displayMessage = extractMessage(responseData) || DEFAULT_REQUEST_ERROR

    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_info')

      const currentPath = window.location.hash
      if (!isHandlingUnauthorized && currentPath !== '#/login') {
        isHandlingUnauthorized = true
        toast.warning(extractMessage(responseData) || DEFAULT_UNAUTHORIZED_MESSAGE, {
          duration: 1200,
        })

        window.setTimeout(() => {
          if (window.location.hash !== '#/login') {
            window.location.hash = '#/login'
          }
          isHandlingUnauthorized = false
        }, 1200)
      }
    }

    // Normalize error message
    error.displayMessage =
      error.response?.status === 401
        ? extractMessage(responseData) || DEFAULT_UNAUTHORIZED_MESSAGE
        : displayMessage

    return Promise.reject(error)
  }
)

export { apiClient }
