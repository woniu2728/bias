import { createListItemRegistry } from './shared.js'


const pageNoteTemplateRegistries = new Map()

function getPageNoteTemplateRegistry(pageKey = '') {
  const normalizedPageKey = String(pageKey || '').trim()
  if (!normalizedPageKey) {
    throw new Error('admin page note template registry requires a page key')
  }

  if (!pageNoteTemplateRegistries.has(normalizedPageKey)) {
    pageNoteTemplateRegistries.set(normalizedPageKey, createListItemRegistry())
  }

  return pageNoteTemplateRegistries.get(normalizedPageKey)
}

export function registerAdminPageNoteTemplate(pageKey, item) {
  return getPageNoteTemplateRegistry(pageKey).register(item)
}

export function getAdminPageNoteTemplates(pageKey, context = {}) {
  return getPageNoteTemplateRegistry(pageKey).get(context)
}
