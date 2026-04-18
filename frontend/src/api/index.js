import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

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
  error => {
    if (error.response?.status === 401) {
      // Token过期，清除本地存储
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      if (typeof window !== 'undefined') {
        const isAdminRuntime =
          window.location.pathname.startsWith('/admin')
          || window.location.pathname.endsWith('/admin.html')

        if (isAdminRuntime) {
          window.location.href = '/login'
        } else {
          window.dispatchEvent(new CustomEvent('bias:auth-required', {
            detail: {
              redirect: `${window.location.pathname}${window.location.search}${window.location.hash}`
            }
          }))
        }
      }
    }
    return Promise.reject(error)
  }
)

export default api
