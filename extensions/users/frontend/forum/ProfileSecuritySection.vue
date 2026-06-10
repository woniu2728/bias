<template>
  <div class="profile-section security-section">
    <div class="profile-section-header">
      <div>
        <h2>{{ securitySectionTitleText }}</h2>
        <p>{{ securitySectionDescriptionText }}</p>
      </div>
    </div>

    <div class="security-grid">
      <section class="profile-settings-card">
        <div class="profile-card-header">
          <div>
            <h3>{{ emailSectionTitleText }}</h3>
            <p>{{ emailSectionDescriptionText }}</p>
          </div>
          <span
            class="email-status"
            :class="{ confirmed: user.is_email_confirmed, pending: !user.is_email_confirmed }"
          >
            {{ emailStatusText }}
          </span>
        </div>

        <div class="email-summary">
          <strong>{{ user.email }}</strong>
          <p>{{ emailHelpText }}</p>
        </div>

        <ForumInlineMessage v-if="verificationSuccess" tone="success">{{ verificationSuccess }}</ForumInlineMessage>
        <ForumInlineMessage v-if="verificationError" tone="danger">{{ verificationError }}</ForumInlineMessage>

        <button
          v-if="!user.is_email_confirmed"
          type="button"
          class="secondary"
          :disabled="verificationSending"
          @click="$emit('resend-verification')"
        >
          {{ resendVerificationButtonText }}
        </button>
      </section>

      <section class="profile-settings-card">
        <div class="profile-card-header">
          <div>
            <h3>{{ passwordSectionTitleText }}</h3>
            <p>{{ passwordSectionDescriptionText }}</p>
          </div>
        </div>

        <ForumInlineMessage v-if="passwordSuccess" tone="success">{{ passwordSuccess }}</ForumInlineMessage>
        <ForumInlineMessage v-if="passwordError" tone="danger">{{ passwordError }}</ForumInlineMessage>

        <div class="profile-form-group">
          <label for="profile-old-password">{{ oldPasswordLabelText }}</label>
          <input
            id="profile-old-password"
            class="profile-form-control"
            :value="passwordForm.old_password"
            name="old_password"
            :placeholder="oldPasswordPlaceholderText"
            type="password"
            @input="$emit('update-password-form', { key: 'old_password', value: $event.target.value })"
          />
        </div>

        <div class="profile-form-group">
          <label for="profile-new-password">{{ newPasswordLabelText }}</label>
          <input
            id="profile-new-password"
            class="profile-form-control"
            :value="passwordForm.new_password"
            name="new_password"
            :placeholder="newPasswordPlaceholderText"
            type="password"
            @input="$emit('update-password-form', { key: 'new_password', value: $event.target.value })"
          />
        </div>

        <div class="profile-form-group">
          <label for="profile-confirm-password">{{ confirmPasswordLabelText }}</label>
          <input
            id="profile-confirm-password"
            class="profile-form-control"
            :value="passwordForm.confirm_password"
            name="confirm_password"
            :placeholder="confirmPasswordPlaceholderText"
            type="password"
            @input="$emit('update-password-form', { key: 'confirm_password', value: $event.target.value })"
          />
        </div>

        <div class="profile-form-actions">
          <button type="button" class="primary" :disabled="changingPassword" @click="$emit('change-password')">
            {{ changePasswordButtonText }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { toRef } from '@bias/core'
import { ForumInlineMessage } from '@bias/forum'
import { useProfileSecuritySectionState } from './useProfileSecuritySectionState'

const props = defineProps({
  user: {
    type: Object,
    required: true
  },
  passwordForm: {
    type: Object,
    required: true
  },
  verificationSending: {
    type: Boolean,
    default: false
  },
  verificationSuccess: {
    type: String,
    default: ''
  },
  verificationError: {
    type: String,
    default: ''
  },
  changingPassword: {
    type: Boolean,
    default: false
  },
  passwordSuccess: {
    type: String,
    default: ''
  },
  passwordError: {
    type: String,
    default: ''
  }
})
const {
  changePasswordButtonText,
  confirmPasswordLabelText,
  confirmPasswordPlaceholderText,
  emailHelpText,
  emailSectionDescriptionText,
  emailSectionTitleText,
  emailStatusText,
  newPasswordLabelText,
  newPasswordPlaceholderText,
  oldPasswordLabelText,
  oldPasswordPlaceholderText,
  passwordSectionDescriptionText,
  passwordSectionTitleText,
  resendVerificationButtonText,
  securitySectionDescriptionText,
  securitySectionTitleText,
} = useProfileSecuritySectionState({
  changingPassword: toRef(props, 'changingPassword'),
  user: toRef(props, 'user'),
  verificationSending: toRef(props, 'verificationSending'),
})

defineEmits(['resend-verification', 'change-password', 'update-password-form'])
</script>

<style scoped>
.security-grid {
  display: grid;
  gap: 18px;
}

.email-summary p {
  color: #6b7a88;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.email-summary {
  margin-bottom: 18px;
}

.email-summary strong {
  color: #24313f;
  overflow-wrap: anywhere;
}

.email-status {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.email-status.confirmed {
  background: #edf8f1;
  color: #1f7a45;
}

.email-status.pending {
  background: #fff3cd;
  color: #856404;
}
</style>
