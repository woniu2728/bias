import {
  registerComposerPreviewTransformer,
  registerComposerTool,
  renderTwemojiHtml,
  setTwemojiBaseUrl,
  setTwemojiEnabled,
} from '@/forum/registry'

function resolveEmojiSettings(context = {}) {
  const settings = context.extension?.forum_settings || context.extension?.settings_values || {}
  return {
    cdnUrl: String(settings.cdn_url || '').trim(),
  }
}

export async function bootForumExtension(context = {}) {
  const emojiSettings = resolveEmojiSettings(context)
  setTwemojiEnabled(true)

  if (emojiSettings.cdnUrl) {
    setTwemojiBaseUrl(emojiSettings.cdnUrl)
  }

  registerComposerTool({
    key: 'emoji',
    moduleId: 'core',
    order: 140,
    title: '表情',
    icon: 'far fa-smile',
  })

  registerComposerPreviewTransformer({
    key: 'emoji-twemoji-preview',
    moduleId: 'core',
    order: 10,
    async transform({ html }) {
      return {
        html: renderTwemojiHtml(html || ''),
      }
    },
  })
}
