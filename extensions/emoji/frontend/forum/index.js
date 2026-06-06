import { Forum } from '@bias/forum'
import {
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

export const extend = [
  buildEmojiForumExtender(),
  new EmojiSettingsExtender(),
]

class EmojiSettingsExtender {
  extend(app) {
    applyEmojiSettings(app)
  }
}

function applyEmojiSettings(app = {}) {
  const emojiSettings = resolveEmojiSettings(app)
  setTwemojiEnabled(true)

  if (emojiSettings.cdnUrl) {
    setTwemojiBaseUrl(emojiSettings.cdnUrl)
  }
}

function buildEmojiForumExtender() {
  const forum = new Forum()
  registerEmojiForum(forum)
  return forum
}

function registerEmojiForum(forum) {
  forum.composerTool({
    key: 'emoji',
    moduleId: 'emoji',
    order: 140,
    title: '表情',
    icon: 'far fa-smile',
  })

  forum.uiCopy({
    key: 'emoji-picker-empty',
    moduleId: 'emoji',
    order: 80,
    surfaces: ['composer-emoji-picker-empty'],
    resolve: () => ({
      text: '没有匹配的表情',
    }),
  })

  forum.uiCopy({
    key: 'emoji-picker-dialog-label',
    moduleId: 'emoji',
    order: 550,
    surfaces: ['composer-emoji-picker-dialog-label'],
    resolve: () => ({
      text: '选择表情',
    }),
  })

  forum.uiCopy({
    key: 'emoji-picker-search-placeholder',
    moduleId: 'emoji',
    order: 560,
    surfaces: ['composer-emoji-picker-search-placeholder'],
    resolve: () => ({
      text: '搜索表情，例如：开心 / heart / fire',
    }),
  })

  forum.uiCopy({
    key: 'emoji-picker-summary',
    moduleId: 'emoji',
    order: 570,
    surfaces: ['composer-emoji-picker-summary'],
    resolve: ({ query, itemCount, activeGroupLabel }) => ({
      text: query
        ? `搜索结果 ${Number(itemCount || 0)} 项`
        : `${activeGroupLabel || '表情'} ${Number(itemCount || 0)} 项`,
    }),
  })

  forum.uiCopy({
    key: 'emoji-autocomplete-label',
    moduleId: 'emoji',
    order: 1090,
    surfaces: ['composer-emoji-autocomplete-label'],
    resolve: () => ({
      text: '表情建议',
    }),
  })

  forum.composerPreviewTransformer({
    key: 'emoji-twemoji-preview',
    moduleId: 'emoji',
    order: 10,
    async transform({ html }) {
      return {
        html: renderTwemojiHtml(html || ''),
      }
    },
  })
}
