import {
  registerAdminMailPageActionMeta,
  registerAdminMailPageConfig,
  registerAdminMailPageCopy,
} from '../pages.js'

registerAdminMailPageCopy({
  key: 'core-mail-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '邮件设置',
    pageDescription: '配置 Gmail 或其他 SMTP 服务的发信参数。',
    loadingText: '加载中...',
    sendabilityWarningText: '当前邮件配置尚不可发送。请先补全发件地址和 SMTP 信息。',
    senderSectionTitle: '发件设置',
    senderSectionDescription: '默认按 Gmail SMTP 预填。若使用 Gmail，密码处需要填写应用专用密码。',
    mailFromLabel: '发件地址',
    mailFromHint: '支持 `your@gmail.com` 或 `Bias <your@gmail.com>`。',
    mailHostLabel: 'SMTP 主机',
    mailPortLabel: 'SMTP 端口',
    mailEncryptionLabel: '加密方式',
    mailEncryptionHint: 'Gmail 通常使用 `TLS + 587`。',
    mailFormatLabel: '邮件格式',
    mailFormatHint: '`Multipart` 兼容性最好。',
    mailUsernameLabel: 'SMTP 用户名',
    mailPasswordLabel: 'SMTP 密码',
    mailPasswordHint: '保存后会按当前输入覆盖运行时密码。',
    saveLabel: '保存设置',
    savingLabel: '保存中...',
    saveSuccessText: '保存成功',
    saveErrorText: '保存失败，请检查当前配置',
  }),
})

registerAdminMailPageConfig({
  key: 'core-mail-page-config',
  order: 10,
  resolve: () => ({
    defaultSettings: {
      mail_from: '',
      mail_format: 'multipart',
      mail_host: 'smtp.gmail.com',
      mail_port: 587,
      mail_encryption: 'tls',
      mail_username: '',
      mail_password: '',
    },
    placeholders: {
      mailFrom: 'Bias <your@gmail.com>',
      mailHost: 'smtp.gmail.com',
      mailPort: '587',
      mailUsername: 'your@gmail.com',
      mailPassword: '应用专用密码',
    },
    encryptionOptions: [
      { value: '', label: '无' },
      { value: 'tls', label: 'TLS' },
      { value: 'ssl', label: 'SSL' },
    ],
    formatOptions: [
      { value: 'multipart', label: 'Multipart' },
      { value: 'plain', label: 'Plain Text' },
      { value: 'html', label: 'HTML' },
    ],
  }),
})

registerAdminMailPageActionMeta({
  key: 'core-mail-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载邮件设置失败，请稍后重试',
    unknownErrorText: '未知错误',
  }),
})
