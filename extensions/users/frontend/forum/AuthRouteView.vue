<template>
  <div class="AuthRouteView" aria-hidden="true"></div>
</template>

<script setup>
import { openForgotPasswordModal, openLoginModal, openRegisterModal, sanitizeRedirectPath } from '@bias/users'
import { useRouter, useRoute } from '@bias/core'

import { useAuthRoutePage } from './useAuthRoutePage'

const route = useRoute()
const router = useRouter()

useAuthRoutePage({
  openForgotPassword: openForgotPasswordModal,
  openLogin: openLoginModal,
  openRegister: openRegisterModal,
  route,
  router,
  sanitizeRedirectPath,
})
</script>
