export function buildAdminExtensionSummaryRequest() {
  return {
    url: '/admin/extensions',
    options: {
      params: { summary: 1 },
    },
  }
}

export async function fetchAdminExtensionSummaries(api) {
  const request = buildAdminExtensionSummaryRequest()
  return api.get(request.url, request.options)
}
