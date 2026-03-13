const BASE = ''

function getToken() {
  return localStorage.getItem('token')
}

async function request<T>(method: string, url: string, body?: unknown, auth = true): Promise<T> {
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
  return resp.json() as Promise<T>
}

export const api = {
  get:    <T>(url: string, auth = true)             => request<T>('GET',    url, undefined, auth),
  post:   <T>(url: string, body: unknown, auth = true) => request<T>('POST',   url, body, auth),
  put:    <T>(url: string, body: unknown)            => request<T>('PUT',    url, body),
  patch:  <T>(url: string, body: unknown)            => request<T>('PATCH',  url, body),
  delete: <T>(url: string)                           => request<T>('DELETE', url),
}
