<template>
  <div class="composer-tag-fields">
    <select
      v-model="primaryTagId"
      class="composer-field composer-tag-select"
      :disabled="submitting || loadingTags || isSuspended"
      @change="handlePrimaryTagChange"
      @keydown.esc.prevent="closeComposer"
    >
      <option value="">{{ primaryTagPlaceholderText }}</option>
      <option v-for="tag in primaryTags" :key="tag.id" :value="String(tag.id)">
        {{ tag.name }}
      </option>
    </select>
    <select
      v-model="secondaryTagId"
      class="composer-field composer-tag-select"
      :disabled="submitting || loadingTags || isSuspended || !secondaryTagOptions.length"
      @change="syncState"
      @keydown.esc.prevent="closeComposer"
    >
      <option value="">{{ secondaryTagPlaceholderText }}</option>
      <option v-for="tag in secondaryTagOptions" :key="tag.id" :value="String(tag.id)">
        {{ tag.name }}
      </option>
    </select>
  </div>
</template>

<script setup>
import { computed, ref, watch } from '@bias/forum'
import { forumApi, getUiCopy } from '@bias/forum'
import { flattenTags, normalizeTag, unwrapTagList } from './tagUtils.js'

const props = defineProps({
  closeComposer: {
    type: Function,
    default: () => {}
  },
  current: {
    type: Object,
    default: () => ({})
  },
  isSuspended: {
    type: Boolean,
    default: false
  },
  requestId: {
    type: [Number, String],
    default: 0
  },
  state: {
    type: Object,
    default: () => ({})
  },
  submitting: {
    type: Boolean,
    default: false
  },
  updateState: {
    type: Function,
    default: () => {}
  }
})

const tags = ref([])
const loadingTags = ref(false)
const primaryTagId = ref('')
const secondaryTagId = ref('')

const availableTags = computed(() => flattenTags(tags.value))
const primaryTags = computed(() => tags.value.filter(tag => !tag.parent_id))
const secondaryTagOptions = computed(() => {
  if (!primaryTagId.value) return []
  const primaryTag = primaryTags.value.find(tag => String(tag.id) === String(primaryTagId.value))
  return primaryTag?.children || []
})
const selectedTagIds = computed(() => {
  return [primaryTagId.value, secondaryTagId.value]
    .filter(Boolean)
    .map(value => parseInt(value, 10))
    .filter(Number.isInteger)
})
const selectedTagLabel = computed(() => {
  const primaryTag = primaryTags.value.find(item => String(item.id) === String(primaryTagId.value))
  const secondaryTag = secondaryTagOptions.value.find(item => String(item.id) === String(secondaryTagId.value))
  return [primaryTag?.name, secondaryTag?.name].filter(Boolean).join(' / ')
})
const primaryTagPlaceholderText = computed(() => getUiCopy({
  surface: 'discussion-composer-primary-tag-placeholder',
  loadingTags: loadingTags.value,
  hasStartableTags: primaryTags.value.length > 0,
})?.text || (loadingTags.value ? '加载标签中...' : (primaryTags.value.length ? '选择主标签' : '暂无可发帖标签')))
const secondaryTagPlaceholderText = computed(() => getUiCopy({
  surface: 'discussion-composer-secondary-tag-placeholder',
  hasSecondaryOptions: secondaryTagOptions.value.length > 0,
})?.text || (secondaryTagOptions.value.length ? '选择次标签（可选）' : '无可用次标签'))

watch(
  () => props.requestId,
  () => prepareField(),
  { immediate: true }
)

async function prepareField() {
  await ensureTagsLoaded()

  primaryTagId.value = String(props.state?.primaryTagId || '')
  secondaryTagId.value = String(props.state?.secondaryTagId || '')
  if (!primaryTagId.value && props.state?.requestedTagId) {
    applyRequestedTag(props.state.requestedTagId)
    return
  }

  handlePrimaryTagChange()
}

async function ensureTagsLoaded() {
  if (loadingTags.value || tags.value.length) return

  loadingTags.value = true
  syncState()
  try {
    const response = await forumApi.get('/tags', {
      params: {
        include_children: true,
        purpose: 'start_discussion',
      },
    })
    tags.value = unwrapTagList(response).map(normalizeTag)
  } catch (error) {
    console.error('加载标签失败:', error)
  } finally {
    loadingTags.value = false
    syncState()
  }
}

function applyRequestedTag(tagId) {
  const requestedTag = availableTags.value.find(tag => String(tag.id) === String(tagId))
  if (!requestedTag) {
    primaryTagId.value = ''
    secondaryTagId.value = ''
    syncState()
    return
  }

  if (requestedTag.parent_id) {
    primaryTagId.value = String(requestedTag.parent_id)
    secondaryTagId.value = String(requestedTag.id)
    syncState()
    return
  }

  primaryTagId.value = String(requestedTag.id)
  handlePrimaryTagChange()
}

function handlePrimaryTagChange() {
  if (!secondaryTagOptions.value.some(option => String(option.id) === String(secondaryTagId.value))) {
    secondaryTagId.value = ''
  }
  syncState()
}

function syncState() {
  props.updateState({
    availablePrimaryTagCount: primaryTags.value.length,
    loadingTags: loadingTags.value,
    primaryTagId: primaryTagId.value,
    secondaryTagId: secondaryTagId.value,
    selectedTagIds: selectedTagIds.value,
    selectedTagLabel: selectedTagLabel.value,
  })
}
</script>

<style scoped>
.composer-tag-fields {
  display: contents;
}
</style>
