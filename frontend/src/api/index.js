import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json'
  }
})

let refreshRequest = null

function clearStoredTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

function isAuthEndpoint(url = '') {
  return url.includes('/users/login')
    || url.includes('/users/logout')
    || url.includes('/users/token/refresh')
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
    const isSessionProbe = requestUrl.includes('/users/me')
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
  config => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
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
        const data = await refreshAccessToken()
        localStorage.setItem('access_token', data.access)
        localStorage.removeItem('refresh_token')

        originalRequest.headers = originalRequest.headers || {}
        originalRequest.headers.Authorization = `Bearer ${data.access}`
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
