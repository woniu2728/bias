import { extendForum } from '@bias/forum'
import { renderTwemojiHtml, setTwemojiBaseUrl, setTwemojiEnabled } from '@bias/emoji'
import ComposerEmojiAutocomplete from './ComposerEmojiAutocomplete.vue'
import ComposerEmojiPicker from './ComposerEmojiPicker.vue'
import { EMOJI_GROUPS, searchEmojiItems } from './emojiData.js'

function resolveEmojiSettings(context = {}) {
  const settings = context.extension?.forum_settings || context.extension?.settings_values || {}
  return {
    cdnUrl: String(settings.cdn_url || '').trim(),
  }
}

export const extend = [
  extendForum(registerEmojiForum),
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

function registerEmojiForum(forum) {
  forum.composerTool({
    key: 'emoji',
    moduleId: 'emoji',
    order: 140,
    title: '表情',
    icon: 'far fa-smile',
    popoverComponent: ComposerEmojiPicker,
    popoverWidth: 420,
    popoverHeight: 360,
    popoverProps: () => ({
      groups: EMOJI_GROUPS,
    }),
  })

  forum.composerAutocompleteProvider({
    key: 'emoji-autocomplete',
    moduleId: 'emoji',
    order: 20,
    renderer: 'emoji',
    component: ComposerEmojiAutocomplete,
    height: 320,
    limit: 8,
    detect({ content = '', cursorPosition }) {
      return detectEmojiQuery(content, cursorPosition)
    },
    search({ query = '', limit = 8 }) {
      return searchEmojiItems(query, {
        limit,
        includeCommonWhenEmpty: true,
      })
    },
    replacement({ item }) {
      return buildEmojiReplacement(item?.emoji)
    },
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

function detectEmojiQuery(content, cursorPosition) {
  const safeContent = String(content || '')
  const safeCursor = Math.max(0, Math.min(cursorPosition ?? safeContent.length, safeContent.length))
  const beforeCursor = safeContent.slice(0, safeCursor)
  const match = beforeCursor.match(/(^|[\s([{"'“‘]):([A-Za-z0-9_+\-\u4e00-\u9fa5]{0,32})$/u)
  if (!match) return null

  const query = match[2] || ''
  const start = safeCursor - query.length - 1
  return {
    query,
    start,
    end: safeCursor
  }
}

function buildEmojiReplacement(emoji) {
  return `${String(emoji || '').trim()} `
}
