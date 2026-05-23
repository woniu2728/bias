import {
  registerAdminBasicsPageActionMeta,
  registerAdminBasicsPageConfig,
  registerAdminBasicsPageCopy,
} from '../pages.js'

registerAdminBasicsPageCopy({
  key: 'core-basics-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '基础设置',
    pageDescription: '配置论坛的基本信息',
    loadingText: '加载基础设置中...',
    forumTitleLabel: '论坛名称',
    forumTitleHelpText: '论坛的名称，显示在页面标题和头部',
    forumDescriptionLabel: '论坛描述',
    forumDescriptionHelpText: '简短描述你的论坛，用于 SEO',
    seoSectionTitle: 'SEO 设置',
    seoSectionDescription: '这些字段会进入公开论坛设置，并在前台页面标题与 meta 标签中生效。',
    seoTitleLabel: 'SEO 标题',
    seoTitleHelpText: '建议控制在 30-60 字符，留空时自动回退到论坛名称。',
    seoDescriptionLabel: 'SEO 描述',
    seoDescriptionHelpText: '建议控制在 80-160 字符，留空时自动回退到论坛描述。',
    seoKeywordsLabel: 'SEO 关键词',
    seoKeywordsHelpText: '使用英文逗号分隔多个关键词，例如：Python, Django, Vue。',
    seoRobotsIndexLabel: '允许搜索引擎建立索引',
    seoRobotsFollowLabel: '允许搜索引擎跟踪页面链接',
    seoNoteText: 'SEO 设置保存后，对外访问的论坛页面通常刷新即可生效；若站点前面接了 CDN 或反向代理缓存，请同步清理缓存。',
    announcementSectionTitle: '站点公告',
    announcementSectionDescription: '在前台顶部展示一条全站公告，适合发布维护预告、运营通知或临时提醒。',
    announcementEnabledLabel: '启用全站公告',
    announcementMessageLabel: '公告内容',
    announcementMessageHelpText: '最多 240 个字符，内容为空时前台不会展示公告。',
    announcementToneLabel: '公告样式',
    saveLabel: '保存设置',
    savingLabel: '保存中...',
    saveSuccessText: '保存成功',
    saveErrorText: '保存失败，请重试',
  }),
})

registerAdminBasicsPageConfig({
  key: 'core-basics-page-config',
  order: 10,
  resolve: () => ({
    defaultSettings: {
      forum_title: '',
      forum_description: '',
      seo_title: '',
      seo_description: '',
      seo_keywords: '',
      seo_robots_index: true,
      seo_robots_follow: true,
      announcement_enabled: false,
      announcement_message: '',
      announcement_tone: 'info',
    },
    placeholders: {
      forumTitle: '我的论坛',
      forumDescription: '一个很棒的社区',
      seoTitle: '留空时使用论坛名称',
      seoDescription: '留空时使用论坛描述',
      seoKeywords: '论坛, 社区, 技术讨论',
      announcementMessage: '例如：今晚 23:00-23:30 将进行短暂维护。',
    },
    announcementToneOptions: [
      { value: 'info', label: '信息' },
      { value: 'warning', label: '提醒' },
      { value: 'success', label: '成功' },
    ],
  }),
})

registerAdminBasicsPageActionMeta({
  key: 'core-basics-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载设置失败，请稍后重试',
  }),
})
