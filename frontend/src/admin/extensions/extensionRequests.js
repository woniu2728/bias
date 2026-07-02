export function buildAdminExtensionSummaryRequest() {
  return {
    url: '/admin/extensions',
    options: {
      params: { summary: 1 },
    },
  }
}

export function buildAdminExtensionDetailListRequest() {
  return {
    url: '/admin/extensions',
    options: {},
  }
}

export async function fetchAdminExtensionSummaries(api) {
  const request = buildAdminExtensionSummaryRequest()
  return api.get(request.url, request.options)
}

export async function fetchAdminExtensionDetailList(api) {
  const request = buildAdminExtensionDetailListRequest()
  return api.get(request.url, request.options)
}
