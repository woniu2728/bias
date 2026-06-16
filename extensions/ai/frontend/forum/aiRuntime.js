export const AI_ACTION_COST_KEYS = Object.freeze({
  questionCoach: 'question_coach',
  summonScribe: 'role_scribe',
  summonDetective: 'role_detective',
  summonChallenger: 'role_challenger',
  bountyJudge: 'bounty_judge',
  discussionSummary: 'discussion_summary',
})

export function getAiModeLabel(result) {
  const mode = String(result?.mode || '').trim()
  if (mode === 'remote') return '远程模型'
  if (mode === 'fallback') return '本地预览'
  if (mode === 'disabled') return '已关闭'
  return ''
}

export function getAiResultTitle(result, fallback = 'AI 反馈') {
  if (result?.action === 'question_coach') return '提问教练'
  if (String(result?.action || '').startsWith('role_')) return 'AI 角色反馈'
  if (result?.action === 'discussion_summary') return '讨论纪要'
  if (result?.action === 'bounty_judge') return '悬赏裁判'
  return fallback
}

export function normalizeAiResultCards(result) {
  return Array.isArray(result?.cards)
    ? result.cards.map(normalizeAiResultCard).filter(card => card.title || card.items.length)
    : []
}

export function normalizeAiResultCard(card) {
  const value = card && typeof card === 'object' ? card : {}
  return {
    title: String(value.title || '').trim(),
    items: normalizeAiResultItems(value.items),
  }
}

export function normalizeAiResultItems(items) {
  return Array.isArray(items)
    ? items.map(item => String(item || '').trim()).filter(Boolean)
    : []
}

export function formatAiResultMarkdown(result) {
  const payload = result && typeof result === 'object' ? result : {}
  const lines = ['> AI 助手建议', '']
  const text = String(payload.text || '').trim()
  if (text) {
    lines.push(text, '')
  }
  for (const card of normalizeAiResultCards(payload)) {
    if (card.title) lines.push(`**${card.title}**`)
    for (const item of card.items) {
      lines.push(`- ${item}`)
    }
    lines.push('')
  }
  return lines.join('\n').trim()
}

export function getAiPointsCost(result) {
  return Number(result?.points?.cost || 0)
}

export function wasAiPointsCharged(result) {
  return Boolean(result?.points?.charged)
}
