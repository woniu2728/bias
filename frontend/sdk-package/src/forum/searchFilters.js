import api from '../api/index.js'

const registeredSearchFilters = []
const searchFilterCatalogPromises = new Map()

function upsertSearchFilter(item) {
  const index = registeredSearchFilters.findIndex(
    existing => existing.key === item.key || (
      existing.target === item.target
      && existing.syntax === item.syntax
      && existing.code === item.code
    )
  )

  if (index >= 0) {
    registeredSearchFilters.splice(index, 1, item)
    return item
  }

  registeredSearchFilters.push(item)
  return item
}

export function registerSearchFilter(item) {
  return upsertSearchFilter({
    order: 100,
    category: 'core',
    ...item,
  })
}

export function getRegisteredSearchFilters(target = '') {
  return [...registeredSearchFilters]
    .filter(item => !target || item.target === target || item.target === 'all')
    .sort((left, right) => (left.order || 100) - (right.order || 100))
}

function normalizeSearchTarget(target = '') {
  const normalized = String(target || '').trim().toLowerCase()
  if (['discussion', 'discussions'].includes(normalized)) return 'discussions'
  if (['post', 'posts'].includes(normalized)) return 'posts'
  return 'all'
}

export async function ensureSearchFilterCatalogLoaded(target = 'all') {
  const normalizedTarget = normalizeSearchTarget(target)

  if (!searchFilterCatalogPromises.has(normalizedTarget)) {
    searchFilterCatalogPromises.set(normalizedTarget, api.get('/search/filters', {
      params: { target: normalizedTarget }
    })
      .then(data => {
        for (const item of data.filters || []) {
          registerSearchFilter({
            key: `${item.target}:${item.code}:${item.syntax}`,
            code: item.code,
            label: item.label,
            target: item.target,
            syntax: item.syntax,
            description: item.description,
            moduleId: item.module_id,
          })
        }
        return getRegisteredSearchFilters()
      })
      .catch(error => {
        searchFilterCatalogPromises.delete(normalizedTarget)
        throw error
      }))
  }

  return searchFilterCatalogPromises.get(normalizedTarget)
}

export function buildSearchFilterQuery(baseQuery, syntax) {
  const normalizedBase = String(baseQuery || '').trim()
  const normalizedSyntax = String(syntax || '').trim()
  if (!normalizedSyntax) return normalizedBase
  if (!normalizedBase) return normalizedSyntax
  if (normalizedBase.includes(normalizedSyntax)) return normalizedBase
  return `${normalizedBase} ${normalizedSyntax}`.trim()
}

export function buildSearchFilterSuggestions(target = '') {
  return getRegisteredSearchFilters(target)
    .filter(item => item.syntax)
    .map(item => ({
      key: `${item.target}:${item.syntax}`,
      label: item.label,
      syntax: item.syntax,
      description: item.description,
      target: item.target,
    }))
}
