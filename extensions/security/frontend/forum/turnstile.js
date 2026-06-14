const TURNSTILE_SCRIPT_ID = 'bias-turnstile-script'
const TURNSTILE_SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

let turnstileScriptPromise = null

export function ensureTurnstileScript() {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Turnstile 只能在浏览器环境加载'))
  }

  if (window.turnstile) {
    return Promise.resolve(window.turnstile)
  }

  if (turnstileScriptPromise) {
    return turnstileScriptPromise
  }

  turnstileScriptPromise = new Promise((resolve, reject) => {
    const existingScript = document.getElementById(TURNSTILE_SCRIPT_ID)
    if (existingScript) {
      existingScript.addEventListener('load', () => resolve(window.turnstile))
      existingScript.addEventListener('error', () => reject(new Error('真人验证脚本加载失败')))
      return
    }

    const script = document.createElement('script')
    script.id = TURNSTILE_SCRIPT_ID
    script.src = TURNSTILE_SCRIPT_SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve(window.turnstile)
    script.onerror = () => reject(new Error('真人验证脚本加载失败'))
    document.head.appendChild(script)
  })

  return turnstileScriptPromise
}
