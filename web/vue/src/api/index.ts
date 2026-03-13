const BASE = ''

type ApiEnvelope<T> = {
  code?: number
  message?: string
  data?: T
}

function unwrapEnvelope<T>(payload: ApiEnvelope<T> | T): T {
  // 兼容后端统一格式：{ code, message, data }
  if (payload && typeof payload === 'object' && 'code' in (payload as Record<string, unknown>)) {
    const env = payload as ApiEnvelope<T>
    if (typeof env.code === 'number' && env.code !== 0) {
      throw new Error(env.message || '请求失败')
    }
    return env.data as T
  }
  return payload as T
}

function getToken() {
  return localStorage.getItem('token')
}

async function request<T>(method: string, url: string, body?: unknown, auth = true): Promise<T> {
  // 统一请求入口：处理鉴权、错误归一化、信封解包。
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (auth) {
    const t = getToken()
    if (t) headers['Authorization'] = `Bearer ${t}`
  }
  const resp = await fetch(BASE + url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined
  })
  if (resp.status === 401) {
    let msg = 'Unauthorized'
    try { const d = await resp.json(); msg = d.message || msg } catch {}
    // 登录接口本身返回 401 时不跳转，否则清 token 并跳转登录页
    if (!url.includes('/auth/login')) {
      localStorage.removeItem('token')
      window.location.hash = '/login'
    }
    throw new Error(msg)
  }
  if (!resp.ok) {
    let msg = resp.statusText
    try { const d = await resp.json(); msg = d.message || msg } catch {
      try { msg = (await resp.text()) || msg } catch {}
    }
    throw new Error(msg)
  }
  const payload = await resp.json() as ApiEnvelope<T> | T
  return unwrapEnvelope(payload)
}

export const api = {
  get:    <T>(url: string, auth = true)             => request<T>('GET',    url, undefined, auth),
  post:   <T>(url: string, body: unknown, auth = true) => request<T>('POST',   url, body, auth),
  put:    <T>(url: string, body: unknown)            => request<T>('PUT',    url, body),
  patch:  <T>(url: string, body: unknown)            => request<T>('PATCH',  url, body),
  delete: <T>(url: string)                           => request<T>('DELETE', url),
}
