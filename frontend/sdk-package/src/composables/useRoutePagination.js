function scrollWindowToTop() {
  if (typeof window !== 'undefined') {
    window.scrollTo(0, 0)
  }
}

export function useRoutePagination({
  page,
  push,
  pageStateKey = 'page',
  scrollAfterNavigate = true,
}) {
  async function navigate(overrides = {}, options = {}) {
    const shouldResetPage = Boolean(options.resetPage)
    const shouldScroll = options.scroll ?? scrollAfterNavigate
    const nextOverrides = { ...overrides }

    if (shouldResetPage) {
      nextOverrides[pageStateKey] = 1
    }

    await push(nextOverrides)

    if (shouldScroll) {
      scrollWindowToTop()
    }
  }

  async function changePage(nextPage, options = {}) {
    if (Number(nextPage) === Number(page?.value || 1)) {
      return false
    }

    await navigate({
      [pageStateKey]: nextPage,
    }, options)

    return true
  }

  async function resetPage(overrides = {}, options = {}) {
    await navigate(overrides, {
      ...options,
      resetPage: true,
    })
  }

  return {
    changePage,
    navigate,
    resetPage,
  }
}
