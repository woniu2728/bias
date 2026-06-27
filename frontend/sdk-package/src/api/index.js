import axios from 'axios'

const CSRF_COOKIE_NAME = 'csrftoken'
const CSRF_HEADER_NAME = 'X-CSRFToken'
const SAFE_HTTP_METHODS = new Set(['get', 'head', 'options', 'trace'])

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json'
  }
})

let refreshRequest = null
let csrfBootstrapRequest = null

function readCookie(name) {
  if (typeof document === 'undefined') return ''

  const prefix = `${name}=`
  const match = document.cookie
    .split(';')
    .map(item => item.trim())
    .find(item => item.startsWith(prefix))

  return match ? decodeURIComponent(match.slice(prefix.length)) : ''
}

function getCsrfToken() {
  return readCookie(CSRF_COOKIE_NAME)
}

function isSafeMethod(method = 'get') {
  return SAFE_HTTP_METHODS.has(String(method || 'get').toLowerCase())
}

async function ensureCsrfCookie() {
  const existingToken = getCsrfToken()
  if (existingToken) return existingToken

  if (!csrfBootstrapRequest) {
    csrfBootstrapRequest = api.get('/csrf', {
      skipAuthRefresh: true,
      skipAuthInvalidation: true,
      skipCsrfBootstrap: true
    }).finally(() => {
      csrfBootstrapRequest = null
    })
  }

  await csrfBootstrapRequest
  return getCsrfToken()
}

export function primeCsrfProtection() {
  return ensureCsrfCookie()
}

function clearStoredTokens() {
  return undefined
}

function isAuthEndpoint(url = '') {
  return url.includes('/users/login')
    || url.includes('/users/logout')
    || url.includes('/users/token/refresh')
    || url.includes('/users/session')
}

async function refreshAccessToken() {
  if (!refreshRequest) {
    refreshRequest = api.post('/users/token/refresh', null, {
      skipAuthRefresh: true,
      skipAuthInvalidation: true
    }).finally(() => {
      refreshRequest = null
    })
  }

  return refreshRequest
}

function notifyAuthInvalidated(error) {
  if (error.config?.skipAuthInvalidation) return

  if (typeof window !== 'undefined') {
    const requestUrl = String(error.config?.url || '')
    const isSessionProbe = requestUrl.includes('/users/me') || requestUrl.includes('/users/session')
    const isAdminRuntime =
      window.location.pathname.startsWith('/admin')
      || window.location.pathname.endsWith('/admin.html')

    window.dispatchEvent(new CustomEvent('bias:auth-invalidated'))

    if (isAdminRuntime) {
      window.location.href = '/login'
    } else if (!isSessionProbe) {
      window.dispatchEvent(new CustomEvent('bias:auth-required', {
        detail: {
          redirect: `${window.location.pathname}${window.location.search}${window.location.hash}`
        }
      }))
    }
  }
}

// 请求拦截器
api.interceptors.request.use(
  async config => {
    const method = String(config.method || 'get').toLowerCase()

    if (!isSafeMethod(method) && !config.skipCsrfBootstrap) {
      const csrfToken = await ensureCsrfCookie()
      if (csrfToken) {
        config.headers = config.headers || {}
        config.headers[CSRF_HEADER_NAME] = csrfToken
      }
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  async error => {
    const originalRequest = error.config || {}
    const requestUrl = String(originalRequest.url || '')

    if (
      error.response?.status === 401
      && !originalRequest._retry
      && !originalRequest.skipAuthRefresh
      && !isAuthEndpoint(requestUrl)
    ) {
      originalRequest._retry = true

      try {
        await refreshAccessToken()
        return api(originalRequest)
      } catch (refreshError) {
        clearStoredTokens()
        notifyAuthInvalidated(error)
        return Promise.reject(refreshError)
      }
    }

    if (error.response?.status === 401) {
      clearStoredTokens()
      notifyAuthInvalidated(error)
    }

    return Promise.reject(error)
  }
)

export default api
