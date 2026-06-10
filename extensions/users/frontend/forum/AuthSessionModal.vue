<template>
  <div class="Modal Modal--small AuthSessionModal fade" :class="{ in: showing }" @click.stop>
    <div class="Modal-content AuthSessionModal-content">
      <div class="Modal-close">
        <button
          type="button"
          class="Button Button--icon Button--link"
          :aria-label="closeLabelText"
          @click="modalStore.dismiss()"
        >
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="Modal-header AuthSessionModal-header">
        <p class="AuthSessionModal-eyebrow">{{ eyebrowText }}</p>
        <h3>{{ titleText }}</h3>
        <p class="AuthSessionModal-subtitle">{{ subtitleText }}</p>
      </div>

      <div class="Modal-body AuthSessionModal-body">
        <form v-if="activeMode === 'login'" class="AuthSessionForm" @submit.prevent="handleLogin">
          <div class="Form-group">
            <label for="auth-login-identification">{{ loginIdentificationLabelText }}</label>
            <input
              id="auth-login-identification"
              ref="loginIdentificationInput"
              v-model.trim="loginForm.identification"
              name="identification"
              class="FormControl"
              type="text"
              :placeholder="loginIdentificationPlaceholderText"
              autocomplete="username"
              :disabled="loading"
              required
            />
          </div>

          <div class="Form-group">
            <label for="auth-login-password">{{ loginPasswordLabelText }}</label>
            <input
              id="auth-login-password"
              v-model="loginForm.password"
              name="password"
              class="FormControl"
              type="password"
              :placeholder="loginPasswordPlaceholderText"
              autocomplete="current-password"
              :disabled="loading"
              required
            />
          </div>

          <div class="AuthSessionRow">
            <label class="AuthSessionCheckbox">
              <input
                v-model="loginForm.remember"
                name="remember"
                type="checkbox"
                :disabled="loading"
              />
              <span>{{ rememberMeText }}</span>
            </label>
            <button type="button" class="AuthSessionLink" :disabled="loading" @click="switchToForgotPassword()">
              {{ forgotPasswordLinkText }}
            </button>
          </div>

          <div v-if="loginHumanVerificationRequired" class="Form-group">
            <div class="AuthSessionFieldLabel">{{ humanVerificationLabelText }}</div>
            <div
              ref="turnstileContainer"
              class="AuthSessionTurnstile"
              :class="{ 'AuthSessionTurnstile--loading': turnstileLoading }"
            ></div>
            <p v-if="turnstileStatusMessage" class="AuthSessionTurnstileStatus">{{ turnstileStatusMessage }}</p>
          </div>

          <div v-if="errorMessage" class="AuthSessionAlert AuthSessionAlert--error">{{ errorMessage }}</div>

          <button type="submit" class="Button Button--primary Button--block" :disabled="loading">
            {{ loginSubmitText }}
          </button>

          <p class="AuthSessionFooter">
            {{ noAccountText }}
            <button
              type="button"
              class="AuthSessionLink"
              :disabled="loading"
              @click="switchToRegister()"
            >
              {{ switchToRegisterText }}
            </button>
          </p>
        </form>

        <form v-else-if="activeMode === 'register'" class="AuthSessionForm" @submit.prevent="handleRegister">
          <div class="Form-group">
            <label for="auth-register-username">{{ registerUsernameLabelText }}</label>
            <input
              id="auth-register-username"
              ref="registerUsernameInput"
              v-model.trim="registerForm.username"
              name="username"
              class="FormControl"
              type="text"
              :placeholder="registerUsernamePlaceholderText"
              autocomplete="username"
              minlength="3"
              maxlength="30"
              :disabled="loading"
              required
            />
          </div>

          <div class="Form-group">
            <label for="auth-register-email">{{ registerEmailLabelText }}</label>
            <input
              id="auth-register-email"
              v-model.trim="registerForm.email"
              name="email"
              class="FormControl"
              type="email"
              :placeholder="registerEmailPlaceholderText"
              autocomplete="email"
              :disabled="loading"
              required
            />
          </div>

          <div class="Form-group">
            <label for="auth-register-password">{{ registerPasswordLabelText }}</label>
            <input
              id="auth-register-password"
              v-model="registerForm.password"
              name="password"
              class="FormControl"
              type="password"
              :placeholder="registerPasswordPlaceholderText"
              autocomplete="new-password"
              minlength="6"
              :disabled="loading"
              required
            />
          </div>

          <div class="Form-group">
            <label for="auth-register-password-confirm">{{ registerPasswordConfirmLabelText }}</label>
            <input
              id="auth-register-password-confirm"
              v-model="registerForm.passwordConfirm"
              name="password_confirm"
              class="FormControl"
              type="password"
              :placeholder="registerPasswordConfirmPlaceholderText"
              autocomplete="new-password"
              :disabled="loading"
              required
            />
          </div>

          <div v-if="registerHumanVerificationRequired" class="Form-group">
            <div class="AuthSessionFieldLabel">{{ humanVerificationLabelText }}</div>
            <div
              ref="turnstileContainer"
              class="AuthSessionTurnstile"
              :class="{ 'AuthSessionTurnstile--loading': turnstileLoading }"
            ></div>
            <p v-if="turnstileStatusMessage" class="AuthSessionTurnstileStatus">{{ turnstileStatusMessage }}</p>
          </div>

          <div v-if="errorMessage" class="AuthSessionAlert AuthSessionAlert--error">{{ errorMessage }}</div>
          <div v-if="successMessage" class="AuthSessionAlert AuthSessionAlert--success">{{ successMessage }}</div>

          <button type="submit" class="Button Button--primary Button--block" :disabled="loading">
            {{ registerSubmitText }}
          </button>

          <p class="AuthSessionFooter">
            {{ hasAccountText }}
            <button
              type="button"
              class="AuthSessionLink"
              :disabled="loading"
              @click="switchToLogin()"
            >
              {{ switchToLoginText }}
            </button>
          </p>
        </form>

        <form v-else class="AuthSessionForm" @submit.prevent="handleForgotPassword">
          <div v-if="forgotPasswordSuccess" class="AuthSessionAlert AuthSessionAlert--success">
            {{ successMessage || forgotPasswordSuccessText }}
          </div>
          <div v-else class="Form-group">
            <label for="auth-forgot-email">{{ forgotEmailLabelText }}</label>
            <input
              id="auth-forgot-email"
              ref="forgotPasswordInput"
              v-model.trim="forgotPasswordEmail"
              name="email"
              class="FormControl"
              type="email"
              :placeholder="forgotEmailPlaceholderText"
              autocomplete="email"
              :disabled="loading"
              required
            />
          </div>

          <div v-if="errorMessage" class="AuthSessionAlert AuthSessionAlert--error">{{ errorMessage }}</div>

          <div v-if="debugResetPath" class="AuthSessionDebugPanel">
            <div class="AuthSessionDebugTitle">{{ debugResetTitleText }}</div>
            <router-link :to="debugResetPath" class="AuthSessionDebugLink" @click="modalStore.dismiss()">
              {{ debugResetPath }}
            </router-link>
          </div>

          <button v-if="!forgotPasswordSuccess" type="submit" class="Button Button--primary Button--block" :disabled="loading">
            {{ forgotSubmitText }}
          </button>
          <button
            v-else
            type="button"
            class="Button Button--primary Button--block"
            @click="switchToLogin({ identification: forgotPasswordEmail })"
          >
            {{ backToLoginText }}
          </button>

          <p v-if="!forgotPasswordSuccess" class="AuthSessionFooter">
            <button
              type="button"
              class="AuthSessionLink"
              :disabled="loading"
              @click="switchToLogin({ identification: forgotPasswordEmail })"
            >
              {{ backToLoginText }}
            </button>
          </p>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  sanitizeRedirectPath,
  useAuthStore } from '@bias/users'
import {
  api,
  watch,
  computed,
  nextTick,
  onBeforeUnmount,
  ref,
  useRouter,
  useModalStore
} from '@bias/core'
import {
  getUiCopy,
  useForumStore
} from '@bias/forum'
import { ensureTurnstileScript } from './turnstile.js'

const props = defineProps({
  showing: {
    type: Boolean,
    default: false
  },
  mode: {
    type: String,
    default: 'login'
  },
  redirectPath: {
    type: String,
    default: '/'
  },
  initialIdentification: {
    type: String,
    default: ''
  },
  initialEmail: {
    type: String,
    default: ''
  },
  initialUsername: {
    type: String,
    default: ''
  },
  initialPassword: {
    type: String,
    default: ''
  }
})

const router = useRouter()
const authStore = useAuthStore()
const forumStore = useForumStore()
const modalStore = useModalStore()

const loginIdentificationInput = ref(null)
const registerUsernameInput = ref(null)
const forgotPasswordInput = ref(null)
const turnstileContainer = ref(null)

const activeMode = ref(normalizeMode(props.mode))
const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const forgotPasswordSuccess = ref(false)
const debugResetUrl = ref('')
const turnstileLoading = ref(false)
const turnstileError = ref('')
const turnstileToken = ref('')
let registerSwitchTimer = null
let turnstileWidgetId = null
let turnstileRenderNonce = 0

const loginForm = ref({
  identification: props.initialIdentification || '',
  password: props.initialPassword || '',
  remember: false
})

const registerForm = ref({
  username: props.initialUsername || '',
  email: props.initialEmail || '',
  password: props.initialPassword || '',
  passwordConfirm: ''
})

const forgotPasswordEmail = ref(props.initialEmail || '')

const turnstileProvider = computed(() => forumStore.settings.auth_human_verification_provider || 'off')
const turnstileSiteKey = computed(() => forumStore.settings.auth_turnstile_site_key || '')
const loginHumanVerificationRequired = computed(() => (
  turnstileProvider.value === 'turnstile'
  && !!turnstileSiteKey.value
  && !!forumStore.settings.auth_human_verification_login_enabled
))
const registerHumanVerificationRequired = computed(() => (
  turnstileProvider.value === 'turnstile'
  && !!turnstileSiteKey.value
  && !!forumStore.settings.auth_human_verification_register_enabled
))
const activeHumanVerificationRequired = computed(() => {
  if (activeMode.value === 'login') return loginHumanVerificationRequired.value
  if (activeMode.value === 'register') return registerHumanVerificationRequired.value
  return false
})
const turnstileStatusMessage = computed(() => {
  if (turnstileError.value) return turnstileError.value
  const uiCopy = getUiCopy({
    surface: 'auth-turnstile-status',
    turnstileLoading: turnstileLoading.value,
    humanVerificationRequired: activeHumanVerificationRequired.value,
    hasToken: Boolean(turnstileToken.value),
  })
  if (uiCopy?.text) return uiCopy.text
  return ''
})
const loginIdentificationPlaceholderText = computed(() => getUiCopy({
  surface: 'auth-login-identification-placeholder',
})?.text || '请输入用户名或邮箱')
const loginPasswordPlaceholderText = computed(() => getUiCopy({
  surface: 'auth-login-password-placeholder',
})?.text || '请输入密码')
const registerUsernamePlaceholderText = computed(() => getUiCopy({
  surface: 'auth-register-username-placeholder',
})?.text || '3-30 个字符')
const registerEmailPlaceholderText = computed(() => getUiCopy({
  surface: 'auth-register-email-placeholder',
})?.text || '请输入邮箱')
const registerPasswordPlaceholderText = computed(() => getUiCopy({
  surface: 'auth-register-password-placeholder',
})?.text || '至少 6 个字符')
const registerPasswordConfirmPlaceholderText = computed(() => getUiCopy({
  surface: 'auth-register-password-confirm-placeholder',
})?.text || '请再次输入密码')
const forgotEmailPlaceholderText = computed(() => getUiCopy({
  surface: 'auth-forgot-email-placeholder',
})?.text || '请输入注册邮箱')
const forgotPasswordSuccessText = computed(() => getUiCopy({
  surface: 'auth-forgot-success',
})?.text || '重置链接已发送，请检查邮箱。')
const debugResetTitleText = computed(() => getUiCopy({
  surface: 'auth-debug-reset-title',
})?.text || '开发环境调试链接')
const loginSubmitText = computed(() => getUiCopy({
  surface: 'auth-login-submit',
  loading: loading.value,
})?.text || (loading.value ? '登录中...' : '登录'))
const registerSubmitText = computed(() => getUiCopy({
  surface: 'auth-register-submit',
  loading: loading.value,
})?.text || (loading.value ? '注册中...' : '注册'))
const forgotSubmitText = computed(() => getUiCopy({
  surface: 'auth-forgot-submit',
  loading: loading.value,
})?.text || (loading.value ? '发送中...' : '发送重置链接'))
const loginIdentificationLabelText = computed(() => getUiCopy({
  surface: 'auth-login-identification-label',
})?.text || '用户名或邮箱')
const loginPasswordLabelText = computed(() => getUiCopy({
  surface: 'auth-login-password-label',
})?.text || '密码')
const humanVerificationLabelText = computed(() => getUiCopy({
  surface: 'auth-human-verification-label',
})?.text || '真人验证')
const registerUsernameLabelText = computed(() => getUiCopy({
  surface: 'auth-register-username-label',
})?.text || '用户名')
const registerEmailLabelText = computed(() => getUiCopy({
  surface: 'auth-register-email-label',
})?.text || '邮箱')
const registerPasswordLabelText = computed(() => getUiCopy({
  surface: 'auth-register-password-label',
})?.text || '密码')
const registerPasswordConfirmLabelText = computed(() => getUiCopy({
  surface: 'auth-register-password-confirm-label',
})?.text || '确认密码')
const forgotEmailLabelText = computed(() => getUiCopy({
  surface: 'auth-forgot-email-label',
})?.text || '邮箱')
const closeLabelText = computed(() => getUiCopy({
  surface: 'auth-session-close',
})?.text || '关闭')
const rememberMeText = computed(() => getUiCopy({
  surface: 'auth-session-remember-me',
})?.text || '记住我')
const forgotPasswordLinkText = computed(() => getUiCopy({
  surface: 'auth-session-forgot-link',
})?.text || '忘记密码？')
const noAccountText = computed(() => getUiCopy({
  surface: 'auth-session-no-account',
})?.text || '还没有账号？')
const switchToRegisterText = computed(() => getUiCopy({
  surface: 'auth-session-switch-register',
})?.text || '立即注册')
const hasAccountText = computed(() => getUiCopy({
  surface: 'auth-session-has-account',
})?.text || '已有账号？')
const switchToLoginText = computed(() => getUiCopy({
  surface: 'auth-session-switch-login',
})?.text || '立即登录')
const backToLoginText = computed(() => getUiCopy({
  surface: 'auth-session-back-login',
})?.text || '返回登录')

const titleText = computed(() => getUiCopy({
  surface: 'auth-session-title',
  mode: activeMode.value,
})?.text || (activeMode.value === 'register' ? '加入讨论' : (activeMode.value === 'forgot-password' ? '找回密码' : '登录')))

const subtitleText = computed(() => getUiCopy({
  surface: 'auth-session-subtitle',
  mode: activeMode.value,
})?.text || (activeMode.value === 'register'
  ? '注册完成后即可回到当前页面继续操作。'
  : (activeMode.value === 'forgot-password'
      ? '输入注册邮箱，我们会向你发送重置密码链接。'
      : '欢迎回来，登录后即可继续回复、关注和管理你的内容。')))

const eyebrowText = computed(() => getUiCopy({
  surface: 'auth-session-eyebrow',
  mode: activeMode.value,
})?.text || (activeMode.value === 'register' ? 'Sign Up' : (activeMode.value === 'forgot-password' ? 'Recovery' : 'Session')))

const debugResetPath = computed(() => {
  if (!debugResetUrl.value) return ''

  try {
    const url = new URL(debugResetUrl.value)
    return `${url.pathname}${url.search}`
  } catch (error) {
    return ''
  }
})

watch(
  () => props.mode,
  mode => {
    activeMode.value = normalizeMode(mode)
    resetMessages()
    queueFocus()
  }
)

watch(
  () => props.showing,
  value => {
    if (value) {
      queueFocus()
      syncTurnstileWidget()
      return
    }

    resetTurnstileWidget()
  },
  { immediate: true }
)

watch(
  () => [
    activeMode.value,
    props.showing,
    activeHumanVerificationRequired.value,
    turnstileSiteKey.value
  ],
  () => {
    syncTurnstileWidget()
  }
)

onBeforeUnmount(() => {
  if (registerSwitchTimer) {
    clearTimeout(registerSwitchTimer)
  }
  resetTurnstileWidget()
})

function normalizeMode(value) {
  return ['login', 'register', 'forgot-password'].includes(value) ? value : 'login'
}

function resetMessages() {
  errorMessage.value = ''
  successMessage.value = ''
  forgotPasswordSuccess.value = false
  debugResetUrl.value = ''
  loading.value = false
}

function resetTurnstileWidget(invalidatePendingRender = true) {
  if (invalidatePendingRender) {
    turnstileRenderNonce += 1
  }
  turnstileToken.value = ''
  turnstileError.value = ''
  turnstileLoading.value = false

  if (typeof window === 'undefined' || !window.turnstile || turnstileWidgetId === null) {
    turnstileWidgetId = null
    return
  }

  try {
    window.turnstile.remove(turnstileWidgetId)
  } catch (error) {
    console.warn('清理真人验证组件失败:', error)
  } finally {
    turnstileWidgetId = null
  }
}

function refreshTurnstileWidget() {
  turnstileToken.value = ''
  turnstileError.value = ''

  if (typeof window === 'undefined' || !window.turnstile || turnstileWidgetId === null) {
    return
  }

  try {
    window.turnstile.reset(turnstileWidgetId)
  } catch (error) {
    console.warn('重置真人验证组件失败:', error)
  }
}

function queueFocus() {
  nextTick(() => {
    requestAnimationFrame(() => {
      if (activeMode.value === 'register') {
        registerUsernameInput.value?.focus()
        return
      }
      if (activeMode.value === 'forgot-password') {
        forgotPasswordInput.value?.focus()
        return
      }
      loginIdentificationInput.value?.focus()
    })
  })
}

function switchToLogin(payload = {}) {
  activeMode.value = 'login'
  resetMessages()
  turnstileError.value = ''
  if (payload.identification) {
    loginForm.value.identification = payload.identification
  } else if (!loginForm.value.identification) {
    loginForm.value.identification = registerForm.value.email || registerForm.value.username || forgotPasswordEmail.value
  }
  queueFocus()
}

function switchToRegister() {
  activeMode.value = 'register'
  resetMessages()
  turnstileError.value = ''

  const identification = loginForm.value.identification.trim()
  if (identification) {
    if (identification.includes('@')) {
      registerForm.value.email = registerForm.value.email || identification
    } else {
      registerForm.value.username = registerForm.value.username || identification
    }
  }

  if (loginForm.value.password && !registerForm.value.password) {
    registerForm.value.password = loginForm.value.password
  }
  queueFocus()
}

function switchToForgotPassword() {
  activeMode.value = 'forgot-password'
  resetMessages()
  resetTurnstileWidget()
  if (!forgotPasswordEmail.value && loginForm.value.identification.includes('@')) {
    forgotPasswordEmail.value = loginForm.value.identification
  }
  queueFocus()
}

async function syncTurnstileWidget() {
  const renderNonce = turnstileRenderNonce + 1
  turnstileRenderNonce = renderNonce
  resetTurnstileWidget(false)

  if (!props.showing || !activeHumanVerificationRequired.value) {
    return
  }

  await nextTick()
  if (!turnstileContainer.value) {
    return
  }

  turnstileLoading.value = true
  turnstileError.value = ''

  try {
    const turnstile = await ensureTurnstileScript()
    if (
      renderNonce !== turnstileRenderNonce
      || !turnstile
      || !turnstileContainer.value
      || !props.showing
      || !activeHumanVerificationRequired.value
    ) {
      turnstileLoading.value = false
      return
    }

    turnstileWidgetId = turnstile.render(turnstileContainer.value, {
      sitekey: turnstileSiteKey.value,
      callback(token) {
        turnstileToken.value = token || ''
        turnstileError.value = ''
      },
      'expired-callback'() {
        turnstileToken.value = ''
        turnstileError.value = getUiCopy({
          surface: 'auth-turnstile-expired-error',
        })?.text || '真人验证已过期，请重新完成验证。'
      },
      'error-callback'() {
        turnstileToken.value = ''
        turnstileError.value = getUiCopy({
          surface: 'auth-turnstile-load-error',
        })?.text || '真人验证加载失败，请稍后重试。'
      }
    })
  } catch (error) {
    turnstileError.value = error.message || getUiCopy({
      surface: 'auth-turnstile-load-error',
    })?.text || '真人验证加载失败，请稍后重试。'
  } finally {
    turnstileLoading.value = false
  }
}

async function handleLogin() {
  loading.value = true
  errorMessage.value = ''

  try {
    const result = await authStore.login(
      loginForm.value.identification,
      loginForm.value.password,
      turnstileToken.value
    )
    if (!result.success) {
      errorMessage.value = result.error || getUiCopy({
        surface: 'auth-login-error',
      })?.text || '登录失败，请检查用户名和密码'
      loginForm.value.password = ''
      if (loginHumanVerificationRequired.value) {
        refreshTurnstileWidget()
      }
      return
    }

    modalStore.close({ authenticated: true })

    const redirect = sanitizeRedirectPath(props.redirectPath)
    if (router.currentRoute.value.fullPath !== redirect) {
      await router.push(redirect)
    }
  } catch (error) {
    errorMessage.value = error.response?.data?.error || getUiCopy({
      surface: 'auth-login-error',
    })?.text || '登录失败，请检查用户名和密码'
    loginForm.value.password = ''
    if (loginHumanVerificationRequired.value) {
      refreshTurnstileWidget()
    }
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''

  if (registerForm.value.password !== registerForm.value.passwordConfirm) {
    errorMessage.value = getUiCopy({
      surface: 'auth-register-password-mismatch-error',
    })?.text || '两次输入的密码不一致'
    loading.value = false
    return
  }

  try {
    const result = await authStore.register(
      registerForm.value.username,
      registerForm.value.email,
      registerForm.value.password,
      turnstileToken.value
    )

    if (!result.success) {
      errorMessage.value = result.error || getUiCopy({
        surface: 'auth-register-error',
      })?.text || '注册失败，请稍后重试'
      if (registerHumanVerificationRequired.value) {
        refreshTurnstileWidget()
      }
      return
    }

    successMessage.value = getUiCopy({
      surface: 'auth-register-success',
    })?.text || '注册成功，请检查邮箱完成验证。'
    if (registerSwitchTimer) {
      clearTimeout(registerSwitchTimer)
    }
    registerSwitchTimer = setTimeout(() => {
      switchToLogin({ identification: registerForm.value.email })
    }, 1200)
  } catch (error) {
    const data = error.response?.data || {}
    if (data.username?.[0]) {
      errorMessage.value = getUiCopy({
        surface: 'auth-register-field-error',
        field: '用户名',
        message: data.username[0],
      })?.text || `用户名: ${data.username[0]}`
    } else if (data.email?.[0]) {
      errorMessage.value = getUiCopy({
        surface: 'auth-register-field-error',
        field: '邮箱',
        message: data.email[0],
      })?.text || `邮箱: ${data.email[0]}`
    } else if (data.password?.[0]) {
      errorMessage.value = getUiCopy({
        surface: 'auth-register-field-error',
        field: '密码',
        message: data.password[0],
      })?.text || `密码: ${data.password[0]}`
    } else {
      errorMessage.value = data.detail || data.error || getUiCopy({
        surface: 'auth-register-error',
      })?.text || '注册失败，请稍后重试'
    }
    if (registerHumanVerificationRequired.value) {
      refreshTurnstileWidget()
    }
  } finally {
    loading.value = false
  }
}

async function handleForgotPassword() {
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  debugResetUrl.value = ''

  try {
    const response = await api.post('/users/forgot-password', {
      email: forgotPasswordEmail.value
    })

    forgotPasswordSuccess.value = true
    successMessage.value = response.message || getUiCopy({
      surface: 'auth-forgot-success',
    })?.text || '重置链接已发送，请检查邮箱。'
    debugResetUrl.value = response.debug_reset_url || ''
  } catch (error) {
    errorMessage.value = error.response?.data?.error || getUiCopy({
      surface: 'auth-forgot-error',
    })?.text || '发送失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.AuthSessionModal {
  width: min(100% - 32px, 460px);
}

.AuthSessionModal-content {
  border: 1px solid rgba(214, 223, 233, 0.72);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(247, 250, 252, 0.96) 100%);
  backdrop-filter: blur(18px);
}

.AuthSessionModal-header {
  padding-bottom: 8px;
}

.AuthSessionModal-eyebrow {
  margin: 0 0 12px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 11px;
  font-weight: 700;
  color: #7a8da2;
}

.AuthSessionModal-subtitle {
  margin: 10px auto 0;
  max-width: 320px;
  color: #667788;
  font-size: 14px;
  line-height: 1.7;
}

.AuthSessionModal-body {
  padding-top: 14px;
}

.AuthSessionForm {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.Form-group {
  margin: 0;
}

.Form-group label {
  display: block;
  margin-bottom: 8px;
  color: #324456;
  font-size: 13px;
  font-weight: 600;
}

.AuthSessionFieldLabel {
  margin-bottom: 8px;
  color: #324456;
  font-size: 13px;
  font-weight: 600;
}

.FormControl {
  width: 100%;
  min-height: 44px;
  border: 1px solid #d7e0e8;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.92);
  font-size: 14px;
  color: #233445;
}

.FormControl:focus {
  border-color: #4d698e;
  box-shadow: 0 0 0 4px rgba(77, 105, 142, 0.12);
}

.AuthSessionRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 24px;
}

.AuthSessionCheckbox {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #596b7d;
  font-size: 13px;
}

.AuthSessionCheckbox input {
  width: auto;
}

.AuthSessionLink {
  padding: 0;
  border: 0;
  background: transparent;
  color: #4d698e;
  font-size: 13px;
  font-weight: 600;
}

.AuthSessionLink:hover:not(:disabled) {
  color: #2f4d72;
  text-decoration: underline;
}

.AuthSessionAlert {
  padding: 12px 14px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
}

.AuthSessionAlert--error {
  background: #fdf0f0;
  color: #b33a3a;
}

.AuthSessionAlert--success {
  background: #edf9f1;
  color: #256b3c;
}

.Button--block {
  width: 100%;
  min-height: 44px;
  border-radius: 10px;
}

.AuthSessionFooter {
  margin: 2px 0 0;
  text-align: center;
  color: #708191;
  font-size: 13px;
}

.AuthSessionDebugPanel {
  background: #f5f8ff;
  border: 1px solid #d7e2ff;
  color: #44556a;
  padding: 12px 14px;
  border-radius: 10px;
  font-size: 13px;
}

.AuthSessionDebugTitle {
  margin-bottom: 8px;
  font-weight: 700;
}

.AuthSessionDebugLink {
  word-break: break-all;
}

.AuthSessionTurnstile {
  min-height: 68px;
  padding: 8px;
  border: 1px solid #d7e0e8;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.92);
}

.AuthSessionTurnstile--loading {
  opacity: 0.75;
}

.AuthSessionTurnstileStatus {
  margin: 8px 0 0;
  color: #708191;
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .AuthSessionModal {
    width: 100%;
  }

  .AuthSessionModal-content {
    min-height: 100dvh;
    border: 0;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(244, 247, 251, 0.98) 100%);
    backdrop-filter: none;
  }

  .AuthSessionRow {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
