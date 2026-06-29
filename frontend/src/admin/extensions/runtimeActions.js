export function resolveRuntimeActionPayload(action) {
  const payload = action?.payload
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return {}
  }
  return { ...payload }
}

export function buildRuntimeActionRequest(extensionId, action) {
  const normalizedExtensionId = String(extensionId || '').trim()
  const actionName = String(action?.action || '').trim()
  if (!normalizedExtensionId || !actionName) {
    return null
  }

  if (actionName.startsWith('hook:')) {
    return {
      url: `/admin/extensions/${normalizedExtensionId}/runtime-hooks/${actionName.slice(5)}`,
      payload: {},
    }
  }

  return {
    url: `/admin/extensions/${normalizedExtensionId}/${actionName}`,
    payload: resolveRuntimeActionPayload(action),
  }
}

export async function postRuntimeAction(api, extensionId, action) {
  const request = buildRuntimeActionRequest(extensionId, action)
  if (!request) {
    return null
  }
  return api.post(request.url, request.payload)
}
