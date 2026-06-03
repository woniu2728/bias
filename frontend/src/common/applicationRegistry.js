const applications = new Map()

export function setRuntimeApplication(kind, app) {
  const normalized = String(kind || 'app').trim()
  if (!normalized || !app) return null
  applications.set(normalized, app)
  return app
}

export function getRuntimeApplication(kind = 'app') {
  return applications.get(String(kind || 'app').trim()) || null
}
