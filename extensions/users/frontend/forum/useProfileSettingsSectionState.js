import {
  computed } from '@bias/core'
import { getStateBlock,
  getUiCopy
} from '@bias/forum'

function getPreferenceGroupFallback(category) {
  return category === 'behavior'
    ? {
        label: '自动关注',
        description: '控制发帖和回帖时的默认关注行为。',
      }
    : {
        label: '通知订阅',
        description: '控制哪些站内通知会推送给你。',
      }
}

export function createProfileSettingsSectionState({
  getState = getStateBlock,
  getText = getUiCopy,
  loadingPreferences,
  preferences,
  saving,
  savingPreferences,
  user,
}) {
  const groupedPreferences = computed(() => {
    const items = Array.isArray(preferences.value?.definitions) ? preferences.value.definitions : []
    const groups = new Map()

    items.forEach(item => {
      const category = String(item.category || 'notification')
      if (!groups.has(category)) {
        const fallback = getPreferenceGroupFallback(category)
        groups.set(category, {
          key: category,
          label: getText({
            surface: 'profile-preferences-group-label',
            category,
          })?.text || fallback.label,
          description: getText({
            surface: 'profile-preferences-group-description',
            category,
          })?.text || fallback.description,
          items: [],
        })
      }
      groups.get(category).items.push(item)
    })

    return Array.from(groups.values())
  })

  const sectionTitleText = computed(() => getText({
    surface: 'profile-settings-section-title',
  })?.text || '个人设置')

  const sectionDescriptionText = computed(() => getText({
    surface: 'profile-settings-section-description',
  })?.text || '维护你的显示名称、邮箱、个人简介和通知偏好。')

  const displayNameLabelText = computed(() => getText({
    surface: 'profile-settings-display-name-label',
  })?.text || '显示名称')

  const emailLabelText = computed(() => getText({
    surface: 'profile-settings-email-label',
  })?.text || '邮箱')

  const bioLabelText = computed(() => getText({
    surface: 'profile-settings-bio-label',
  })?.text || '个人简介')

  const preferencesTitleText = computed(() => getText({
    surface: 'profile-preferences-section-title',
  })?.text || '通知偏好')

  const preferencesDescriptionText = computed(() => getText({
    surface: 'profile-preferences-section-description',
  })?.text || '按模块统一管理自动关注和通知订阅，新增通知类型后可以直接从注册表接入这里。')

  const preferencesLoadingStateText = computed(() => {
    const stateBlock = getState({
      surface: 'profile-preferences-loading',
      loading: loadingPreferences.value,
      preferences: preferences.value,
    })

    return stateBlock?.text || '加载偏好中...'
  })

  const displayNamePlaceholderText = computed(() => getText({
    surface: 'profile-settings-display-name-placeholder',
  })?.text || '显示名称')

  const emailPlaceholderText = computed(() => getText({
    surface: 'profile-settings-email-placeholder',
  })?.text || 'name@example.com')

  const bioPlaceholderText = computed(() => getText({
    surface: 'profile-settings-bio-placeholder',
  })?.text || '介绍一下自己...')

  const emailHelpText = computed(() => getText({
    surface: 'profile-settings-email-help',
    isEmailConfirmed: user.value?.is_email_confirmed,
  })?.text || (user.value?.is_email_confirmed ? '当前邮箱已完成验证。' : '修改邮箱后会重新进入未验证状态。'))

  const saveProfileButtonText = computed(() => getText({
    surface: 'profile-settings-save-button',
    saving: saving.value,
  })?.text || (saving.value ? '保存中...' : '保存资料'))

  const savePreferencesButtonText = computed(() => getText({
    surface: 'profile-preferences-save-button',
    saving: savingPreferences.value,
  })?.text || (savingPreferences.value ? '保存中...' : '保存偏好'))

  return {
    bioLabelText,
    bioPlaceholderText,
    displayNameLabelText,
    displayNamePlaceholderText,
    emailHelpText,
    emailLabelText,
    emailPlaceholderText,
    groupedPreferences,
    preferencesDescriptionText,
    preferencesLoadingStateText,
    preferencesTitleText,
    savePreferencesButtonText,
    saveProfileButtonText,
    sectionDescriptionText,
    sectionTitleText,
  }
}

export function useProfileSettingsSectionState(options) {
  return createProfileSettingsSectionState(options)
}
