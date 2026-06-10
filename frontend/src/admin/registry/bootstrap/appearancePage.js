import {
  registerAdminAppearancePageActionMeta,
  registerAdminAppearancePageConfig,
  registerAdminAppearancePageCopy,
} from '../pages.js'

registerAdminAppearancePageCopy({
  key: 'core-appearance-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '外观设置',
    pageDescription: '自定义论坛的外观和主题',
    loadingText: '加载外观配置中...',
    colorsSectionTitle: '颜色',
    primaryColorLabel: '主题色',
    primaryColorPickerAriaLabel: '主题色取色器',
    primaryColorHelpText: '论坛的主题颜色',
    accentColorLabel: '强调色',
    accentColorPickerAriaLabel: '强调色取色器',
    accentColorHelpText: '用于按钮和链接的强调色',
    brandingSectionTitle: 'Logo 与图标',
    logoPreviewAlt: 'Logo 预览',
    logoEmptyText: '暂无 Logo',
    logoCardTitle: '站点 Logo',
    logoHelpText: '建议上传透明背景 PNG、SVG 或 WebP，Header 会优先展示这里的资源。',
    clearAssetLabel: '清空',
    logoUrlLabel: 'Logo URL',
    logoUrlHelpText: '论坛 Logo 的 URL 地址',
    faviconPreviewAlt: 'Favicon 预览',
    faviconEmptyText: '暂无 Favicon',
    faviconCardTitle: '浏览器图标',
    faviconHelpText: '建议上传 `.ico`、PNG 或 SVG，小尺寸图标在浏览器标签页里更清晰。',
    faviconUrlLabel: 'Favicon URL',
    faviconUrlHelpText: '浏览器标签页图标的 URL 地址',
    customStyleSectionTitle: '自定义样式',
    customHeadLabel: 'Head / 统计代码注入',
    customHeadHelpText: '用于统计脚本、验证标签或其他不直接展示给用户的 Head 注入。',
    customFooterLabel: 'Footer HTML',
    customFooterHelpText: '这里的内容会直接显示在站点页脚，适合备案、版权和联系信息。',
    saveLabel: '保存设置',
    savingLabel: '保存中...',
    saveSuccessText: '保存成功',
    saveErrorText: '保存失败，请重试',
  }),
})

registerAdminAppearancePageConfig({
  key: 'core-appearance-page-config',
  order: 10,
  resolve: () => ({
    defaultSettings: {
      primary_color: '#4d698e',
      accent_color: '#e74c3c',
      logo_url: '',
      favicon_url: '',
      custom_head_html: '',
      custom_footer_html: '',
    },
    placeholders: {
      primaryColor: '#4d698e',
      accentColor: '#e74c3c',
      logoUrl: 'https://example.com/logo.png',
      faviconUrl: 'https://example.com/favicon.ico',
      customHead: '<!-- 在这里添加 head 注入或统计代码 -->',
      customFooter: '<p>在页脚展示备案号、版权说明或联系信息</p>',
    },
  }),
})

registerAdminAppearancePageActionMeta({
  key: 'core-appearance-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载外观设置失败，请稍后重试',
  }),
})
