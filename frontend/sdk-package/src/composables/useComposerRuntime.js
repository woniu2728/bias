import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { runComposerSecondaryAction } from '../forum/composerRuntime.js'
import {
  getComposerAutocompleteProviders,
  getComposerDraftMeta,
  getComposerNotices,
  getComposerSecondaryActions,
  getComposerStatusItems,
  getComposerTools,
  getComposerUploadHandler,
  getUiCopy,
  runComposerPreviewTransformers,
} from '../forum/registry.js'
import {
  BASE_COMPOSER_TOOLS,
  buildComposerToolReplacement,
  defaultToolCursorOffset,
  fetchComposerPreview,
  getComposerErrorMessage,
  getTextareaCaretCoordinates,
  replaceSelection,
} from '../utils/composer.js'

function sortByOrder(items) {
  return [...items].sort((left, right) => (left.order || 100) - (right.order || 100))
}

export function useComposerRuntime(options = {}) {
  const {
    composerStore,
    showComposer,
    content,
    submitting,
    submit,
    closeComposer,
    buildBaseContext,
    focusEditor,
    openComposer = () => composerStore?.showComposer?.(),
    saveRequestType = '',
    onSaveRequest = null,
    height = {},
  } = options

  const composerTextarea = ref(null)
  const attachmentInput = ref(null)
  const imageInput = ref(null)

  const uploading = ref(false)
  const uploadNotice = ref('')
  const uploadNoticeTone = ref('info')
  const activeToolPopoverKey = ref('')
  const activeToolPopoverAnchor = ref(null)
  const autocompleteItems = ref([])
  const autocompleteState = ref(null)
  const autocompleteCaret = ref(null)
  const autocompleteProvider = ref(null)
  const autocompleteLoading = ref(false)
  const autocompleteActiveIndex = ref(0)
  const showPreview = ref(false)
  const previewHtml = ref('')
  const previewLoading = ref(false)
  const previewError = ref('')
  const composerHeight = ref(loadComposerHeight())
  const resizing = ref(false)
  const viewportWidth = ref(typeof window === 'undefined' ? 1280 : window.innerWidth)

  let resizeStartY = 0
  let resizeStartHeight = composerHeight.value
  let previewTimer = null
  let autocompleteTimer = null
  let autocompleteRequestId = 0

  const isPhoneViewport = computed(() => viewportWidth.value <= 768)
  const isPhoneOverlay = computed(() => isPhoneViewport.value && showComposer.value && !composerStore.isMinimized)
  const showBackdrop = computed(() => isPhoneOverlay.value)
  const activeToolPopover = computed(() => {
    const key = activeToolPopoverKey.value
    if (!key) return null

    const tool = composerTools.value.find(item => item.key === key)
    const component = tool?.popoverComponent || tool?.popover_component
    if (!tool || !component) return null

    const componentProps = typeof tool.popoverProps === 'function'
      ? tool.popoverProps(buildToolContext(tool))
      : (tool.popoverProps || tool.popover_props || {})

    return {
      key,
      tool,
      component,
      componentProps: componentProps && typeof componentProps === 'object' ? componentProps : {},
      styleObject: buildFloatingPickerStyle(
        getToolPopoverAnchor(),
        Number(tool.popoverHeight || tool.popover_height || tool.preferredHeight || 320),
        Number(tool.popoverWidth || tool.popover_width || 420)
      ),
    }
  })
  const activeAutocomplete = computed(() => {
    const provider = autocompleteProvider.value
    const state = autocompleteState.value
    if (!provider || !state || !provider.component) {
      return null
    }

    const showWhenEmpty = Boolean(provider.showWhenEmpty || provider.show_when_empty)
    if (!autocompleteLoading.value && autocompleteItems.value.length <= 0 && !showWhenEmpty) {
      return null
    }

    return {
      key: state.providerKey || provider.key,
      provider,
      state,
      component: provider.component,
      items: autocompleteItems.value,
      activeIndex: autocompleteActiveIndex.value,
      loading: autocompleteLoading.value,
      styleObject: buildFloatingPickerStyle(autocompleteCaret.value, Number(provider.height || provider.preferredHeight || 320)),
    }
  })
  const showAutocomplete = computed(() => {
    return Boolean(activeAutocomplete.value)
  })
  const composerInlineStyle = computed(() => {
    if (composerStore.isMinimized || composerStore.isExpanded || isPhoneOverlay.value) return {}
    return { height: `${composerHeight.value}px` }
  })
  const composerTools = computed(() => {
    return sortByOrder([
      ...BASE_COMPOSER_TOOLS,
      ...getComposerTools(buildExtensionContext()),
    ])
  })
  const composerSecondaryActions = computed(() => {
    return getComposerSecondaryActions(buildExtensionContext())
  })
  const composerStatusItems = computed(() => {
    return sortByOrder([
      ...getComposerStatusItems(buildExtensionContext()),
      ...getComposerDraftMeta(buildExtensionContext()),
    ])
  })
  const composerExtensionNotices = computed(() => {
    return getComposerNotices(buildExtensionContext())
  })

  watch(content, () => {
    schedulePreview()
  })

  watch(
    [
      showComposer,
      () => composerStore.isMinimized,
      () => composerStore.isExpanded,
      composerHeight,
      isPhoneViewport,
    ],
    () => {
      syncComposerViewportEffects()
    },
    { immediate: true }
  )

  onMounted(() => {
    window.addEventListener('resize', handleViewportResize)
    window.addEventListener('mousemove', handleResizeMove)
    window.addEventListener('mouseup', stopResize)
    document.addEventListener('mousedown', handleDocumentMouseDown)
    window.addEventListener('bias:composer-save-request', handleComposerSaveRequest)
  })

  onBeforeUnmount(() => {
    clearPreviewTimer()
    clearInlineSuggestions()
    window.removeEventListener('resize', handleViewportResize)
    window.removeEventListener('mousemove', handleResizeMove)
    window.removeEventListener('mouseup', stopResize)
    document.removeEventListener('mousedown', handleDocumentMouseDown)
    window.removeEventListener('bias:composer-save-request', handleComposerSaveRequest)
    clearComposerViewportEffects()
  })

  function buildExtensionContext(extra = {}) {
    return {
      ...(typeof buildBaseContext === 'function' ? buildBaseContext() : {}),
      ...extra,
      composerStore,
      content: content.value,
      isExpanded: composerStore.isExpanded,
      isMinimized: composerStore.isMinimized,
      minimized: composerStore.isMinimized,
      showPreview: showPreview.value,
      submitting: Boolean(submitting?.value),
      uploading: uploading.value,
    }
  }

  function buildToolContext(tool) {
    const textarea = composerTextarea.value
    return buildExtensionContext({
      tool,
      clearInlineSuggestions() {
        clearInlineSuggestions()
      },
      focusEditor() {
        focusEditor?.()
      },
      insertText: insertComposerText,
      openAttachmentPicker() {
        attachmentInput.value?.click()
      },
      openImagePicker() {
        imageInput.value?.click()
      },
      selectionEnd: textarea?.selectionEnd ?? content.value.length,
      selectionStart: textarea?.selectionStart ?? content.value.length,
      setToolPopoverVisible(value) {
        setToolPopoverVisible(tool, Boolean(value))
      },
      setPreviewVisible(value) {
        showPreview.value = Boolean(value)
      },
    })
  }

  async function applyComposerTool(tool, event = null) {
    openComposer?.()
    await nextTick()

    if (typeof tool.run === 'function') {
      await tool.run(buildToolContext(tool))
      return
    }

    if (tool.key === 'upload') {
      closeToolPopover()
      clearInlineSuggestions()
      attachmentInput.value?.click()
      return
    }
    if (tool.key === 'image') {
      closeToolPopover()
      clearInlineSuggestions()
      imageInput.value?.click()
      return
    }

    if (tool.popoverComponent || tool.popover_component) {
      clearInlineSuggestions()
      if (showPreview.value) {
        showPreview.value = false
        await nextTick()
      }
      activeToolPopoverAnchor.value = event?.currentTarget || null
      setToolPopoverVisible(tool, activeToolPopoverKey.value !== tool.key)
      if (activeToolPopoverKey.value === tool.key) {
        focusEditor?.()
      }
      return
    }

    const textarea = composerTextarea.value
    if (!textarea) return

    const start = textarea.selectionStart ?? content.value.length
    const end = textarea.selectionEnd ?? content.value.length
    const selected = content.value.slice(start, end)
    const replacement = buildComposerToolReplacement(tool, selected)
    const cursor = selected ? start + replacement.length : start + defaultToolCursorOffset(tool)

    await insertComposerText(replacement, { start, end, cursor })
  }

  function handleEditorInteraction(event) {
    if (
      event?.type === 'keyup'
      && ['ArrowUp', 'ArrowDown', 'Enter', 'Escape', 'Tab'].includes(event.key)
    ) {
      return
    }
    syncInlineSuggestions()
  }

  function handleEditorKeydown(event) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault()
      submit?.()
      return
    }

    if (event.key === 'Escape') {
      if (showAutocomplete.value) {
        event.preventDefault()
        clearInlineSuggestions()
        return
      }
      if (activeToolPopover.value) {
        event.preventDefault()
        closeToolPopover()
        return
      }
      if (showPreview.value) {
        event.preventDefault()
        showPreview.value = false
        nextTick(() => focusEditor?.())
        return
      }
      event.preventDefault()
      closeComposer?.()
      return
    }

    if (showAutocomplete.value) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        autocompleteActiveIndex.value =
          (autocompleteActiveIndex.value + 1) % Math.max(autocompleteItems.value.length, 1)
        return
      }

      if (event.key === 'ArrowUp') {
        event.preventDefault()
        autocompleteActiveIndex.value =
          (autocompleteActiveIndex.value - 1 + Math.max(autocompleteItems.value.length, 1)) % Math.max(autocompleteItems.value.length, 1)
        return
      }

      if (
        shouldAcceptAutocompleteKey(event.key)
        && !event.shiftKey
        && !event.ctrlKey
        && !event.metaKey
        && !event.altKey
      ) {
        const activeItem = autocompleteItems.value[autocompleteActiveIndex.value]
        if (!activeItem) return
        event.preventDefault()
        handleAutocompleteSelect(activeItem)
        return
      }

      if (event.key === 'Escape') {
        clearInlineSuggestions()
      }
    }
  }

  async function handleAttachmentSelected(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    await uploadAndInsertFile(file, false)
  }

  async function handleImageSelected(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    await uploadAndInsertFile(file, true)
  }

  async function uploadAndInsertFile(file, asImage) {
    uploading.value = true
    uploadNoticeTone.value = 'info'
    uploadNotice.value = getUiCopy({
      surface: 'composer-upload-progress',
      asImage,
      fileName: file.name,
    })?.text || `正在上传${asImage ? '图片' : '附件'}：${file.name}`

    try {
      const handlerContext = buildExtensionContext({
        asImage,
        file,
        fileName: file.name,
      })
      const handler = getComposerUploadHandler(handlerContext)
      if (!handler) {
        throw new Error(getUiCopy({
          surface: 'composer-upload-unavailable',
          asImage,
        })?.text || '上传功能未启用')
      }

      const uploaded = await handler.upload(handlerContext)
      if (!showComposer.value) return

      const markdown = String(uploaded?.markdown || '').trim()
      if (!markdown) {
        throw new Error(getUiCopy({
          surface: 'composer-upload-failed',
          asImage,
        })?.text || (asImage ? '图片上传失败' : '附件上传失败'))
      }
      await insertComposerText(markdown)
      uploadNoticeTone.value = 'success'
      uploadNotice.value = getUiCopy({
        surface: 'composer-upload-inserted',
        asImage,
      })?.text || `${asImage ? '图片' : '附件'}已插入编辑器`
    } catch (error) {
      uploadNoticeTone.value = 'error'
      uploadNotice.value = getComposerErrorMessage(error, getUiCopy({
        surface: 'composer-upload-failed',
        asImage,
      })?.text || (asImage ? '图片上传失败' : '附件上传失败'))
    } finally {
      uploading.value = false
    }
  }

  function syncInlineSuggestions() {
    if (showPreview.value) {
      clearInlineSuggestions()
      return
    }

    const textarea = composerTextarea.value
    if (!textarea || textarea.selectionStart !== textarea.selectionEnd) {
      clearInlineSuggestions()
      return
    }

    const cursorPosition = textarea.selectionStart
    const context = buildExtensionContext({
      cursorPosition,
      selectionStart: cursorPosition,
      selectionEnd: cursorPosition,
    })
    const providers = getComposerAutocompleteProviders(context)

    for (const provider of providers) {
      if (typeof provider.detect !== 'function') {
        continue
      }
      const detected = provider.detect(context)
      if (!detected) {
        continue
      }
      activateAutocompleteProvider(provider, detected, textarea)
      return
    }

    clearInlineSuggestions()
  }

  function activateAutocompleteProvider(provider, detected, textarea) {
    const renderer = normalizeAutocompleteRenderer(provider)
    const state = {
      ...detected,
      providerKey: provider.key,
      renderer,
    }
    const caret = getTextareaCaretCoordinates(textarea, state.start)

    clearAutocomplete()
    autocompleteProvider.value = provider
    autocompleteState.value = state
    autocompleteCaret.value = caret
    scheduleAutocompleteSearch(provider, state)
  }

  function scheduleAutocompleteSearch(provider, state) {
    if (autocompleteTimer) {
      clearTimeout(autocompleteTimer)
    }

    const renderer = state.renderer
    autocompleteLoading.value = typeof provider.search === 'function'
    const requestId = ++autocompleteRequestId
    const delay = Number(provider.debounce ?? provider.debounceMs ?? 0)

    autocompleteTimer = setTimeout(async () => {
      try {
        const items = typeof provider.search === 'function'
          ? await provider.search(buildExtensionContext({
              autocomplete: state,
              autocompleteProvider: provider,
              query: state.query || '',
              limit: Number(provider.limit || 8),
            }))
          : []
        if (requestId !== autocompleteRequestId || !isAutocompleteProviderActive(provider)) return
        applyAutocompleteItems(provider, Array.isArray(items) ? items : [])
      } catch (error) {
        if (requestId !== autocompleteRequestId) return
        applyAutocompleteItems(provider, [])
      } finally {
        if (requestId === autocompleteRequestId) {
          autocompleteLoading.value = false
        }
      }
    }, Math.max(0, delay))
  }

  async function handleAutocompleteSelect(item) {
    if (!autocompleteState.value || !item) return

    const replacement = resolveAutocompleteReplacement(autocompleteProvider.value, item, autocompleteState.value)
    if (!replacement) return
    await insertComposerText(replacement, {
      start: autocompleteState.value.start,
      end: autocompleteState.value.end,
      cursor: autocompleteState.value.start + replacement.length,
    })
    clearAutocomplete()
  }

  function handleAutocompleteHighlight(index) {
    autocompleteActiveIndex.value = Number(index) || 0
  }

  function togglePreview() {
    showPreview.value = !showPreview.value
    previewError.value = ''
    closeToolPopover()
    clearInlineSuggestions()

    if (showPreview.value) {
      requestPreview()
      return
    }

    nextTick(() => focusEditor?.())
  }

  function schedulePreview() {
    if (!showPreview.value) return

    clearPreviewTimer()
    previewTimer = setTimeout(() => {
      requestPreview()
    }, 220)
  }

  async function requestPreview() {
    if (!showPreview.value) return

    const currentContent = content.value.trim()
    previewError.value = ''
    if (!currentContent) {
      previewHtml.value = ''
      previewLoading.value = false
      return
    }

    previewLoading.value = true
    try {
      const data = await fetchComposerPreview(content.value)
      if (!showPreview.value) return
      const transformed = await runComposerPreviewTransformers(buildExtensionContext({
        content: content.value,
        data,
        html: data.html || '',
      }))
      previewHtml.value = transformed?.html || data.html || ''
    } catch (error) {
      previewError.value = getComposerErrorMessage(error, getUiCopy({
        surface: 'composer-preview-load-failed',
      })?.text || '预览加载失败')
    } finally {
      previewLoading.value = false
    }
  }

  async function insertComposerText(replacement, options = {}) {
    await nextTick()

    const textarea = composerTextarea.value
    const currentContent = content.value
    const start = options.start ?? textarea?.selectionStart ?? currentContent.length
    const end = options.end ?? textarea?.selectionEnd ?? currentContent.length
    const cursor = options.cursor ?? start + replacement.length

    content.value = replaceSelection(currentContent, start, end, replacement)

    await nextTick()
    focusEditor?.()
    composerTextarea.value?.setSelectionRange(cursor, cursor)
    syncInlineSuggestions()
  }

  function handleDocumentMouseDown(event) {
    if (activeToolPopover.value && !getToolPopoverAnchorElement()?.contains(event.target)) {
      closeToolPopover()
    }
    if (event.target !== composerTextarea.value) {
      clearInlineSuggestions()
    }
  }

  function clearPreviewTimer() {
    if (previewTimer) {
      clearTimeout(previewTimer)
      previewTimer = null
    }
  }

  function clearAutocomplete() {
    autocompleteLoading.value = false
    autocompleteItems.value = []
    autocompleteState.value = null
    autocompleteCaret.value = null
    autocompleteProvider.value = null
    autocompleteActiveIndex.value = 0
  }

  function clearInlineSuggestions() {
    if (autocompleteTimer) {
      clearTimeout(autocompleteTimer)
      autocompleteTimer = null
    }
    autocompleteRequestId += 1
    clearAutocomplete()
  }

  function clearRuntimeState() {
    uploadNotice.value = ''
    uploadNoticeTone.value = 'info'
    closeToolPopover()
    showPreview.value = false
    previewHtml.value = ''
    previewLoading.value = false
    previewError.value = ''
    clearPreviewTimer()
    clearInlineSuggestions()
  }

  function handleViewportResize() {
    viewportWidth.value = window.innerWidth
    if (autocompleteState.value) {
      nextTick(() => {
        syncInlineSuggestions()
      })
    }
  }

  function normalizeAutocompleteRenderer(provider = {}) {
    const renderer = String(provider.renderer || provider.type || provider.kind || '').trim()
    return renderer === 'emoji' ? 'emoji' : 'mention'
  }

  function isAutocompleteProviderActive(provider) {
    return autocompleteProvider.value?.key === provider.key && Boolean(autocompleteState.value)
  }

  function applyAutocompleteItems(provider, items) {
    const limit = Number(provider.limit || 8)
    const normalizedItems = items.slice(0, Math.max(1, limit))
    autocompleteItems.value = normalizedItems
    autocompleteActiveIndex.value = 0
  }

  function resolveAutocompleteReplacement(provider, item, state) {
    if (!provider) return ''
    const context = buildExtensionContext({
      autocomplete: state,
      autocompleteProvider: provider,
      item,
      query: state?.query || '',
    })
    if (typeof provider.replacement === 'function') {
      return String(provider.replacement(context) || '')
    }
    if (typeof item?.replacement === 'function') {
      return String(item.replacement(context) || '')
    }
    if (typeof item?.replacement === 'string') {
      return item.replacement
    }
    if (typeof item?.emoji === 'string') {
      return `${item.emoji.trim()} `
    }
    if (typeof item?.username === 'string') {
      return `@${item.username.trim()} `
    }
    return ''
  }

  function shouldAcceptAutocompleteKey(key) {
    const provider = autocompleteProvider.value
    const configuredKeys = provider?.acceptKeys || provider?.accept_keys || provider?.selectionKeys || provider?.selection_keys
    const keys = Array.isArray(configuredKeys) && configuredKeys.length
      ? configuredKeys
      : ['Enter', 'Tab']
    return keys.includes(key)
  }

  function startResize(event) {
    if (composerStore.isExpanded || composerStore.isMinimized || window.innerWidth <= 768) return

    resizing.value = true
    resizeStartY = event.clientY
    resizeStartHeight = composerHeight.value
  }

  function handleResizeMove(event) {
    if (!resizing.value) return

    const delta = resizeStartY - event.clientY
    composerHeight.value = clampComposerHeight(resizeStartHeight + delta)
  }

  function stopResize() {
    if (!resizing.value) return
    resizing.value = false
    persistComposerHeight(composerHeight.value)
  }

  function syncComposerViewportEffects() {
    if (typeof document === 'undefined') return
    if (composerStore.isOpen && !showComposer.value) return

    const activeDesktopComposer =
      showComposer.value
      && !composerStore.isMinimized
      && !composerStore.isExpanded
      && !isPhoneViewport.value

    document.documentElement.style.setProperty('--composer-offset', activeDesktopComposer ? `${composerHeight.value + 24}px` : '0px')
    document.body.style.overflow = showBackdrop.value ? 'hidden' : ''
  }

  function clearComposerViewportEffects() {
    if (typeof document === 'undefined') return
    document.documentElement.style.setProperty('--composer-offset', '0px')
    document.body.style.overflow = ''
  }

  function handleComposerSaveRequest(event) {
    if (!saveRequestType || typeof onSaveRequest !== 'function') return

    const detail = event?.detail || {}
    if (detail.composerType !== saveRequestType) return
    if (Number(detail.requestId || 0) !== Number(composerStore.current.requestId || 0)) return
    onSaveRequest(true)
  }

  async function handleComposerSecondaryAction(item) {
    await runComposerSecondaryAction(item, buildExtensionContext())
  }

  function loadComposerHeight() {
    if (typeof window === 'undefined') {
      return Number(height.defaultValue || 420)
    }
    const value = Number(window.localStorage.getItem(height.storageKey) || height.defaultValue || 420)
    return clampComposerHeight(value)
  }

  function persistComposerHeight(value) {
    if (typeof window === 'undefined' || !height.storageKey) return
    window.localStorage.setItem(height.storageKey, String(clampComposerHeight(value)))
  }

  function clampComposerHeight(value) {
    const min = Number(height.min || 280)
    const fallbackMax = Number(height.maxDefault || 680)
    const windowMax = typeof window === 'undefined'
      ? fallbackMax
      : Math.max(Number(height.maxFloor || 320), window.innerHeight - Number(height.windowOffset || 72))
    return Math.max(min, Math.min(value, windowMax))
  }

  function buildFloatingPickerStyle(anchor, preferredHeight, preferredWidth = 320) {
    if (!anchor || typeof window === 'undefined') return {}

    const pickerWidth = Math.min(preferredWidth, Math.max(240, window.innerWidth - 32))
    const pickerHeight = Math.min(preferredHeight, Math.max(180, window.innerHeight - 32))
    const left = Math.max(16, Math.min(anchor.left, window.innerWidth - pickerWidth - 16))
    const lineHeight = Number(anchor.lineHeight || anchor.height || 20)
    const belowTop = anchor.top + lineHeight + 8
    const openAbove = belowTop + pickerHeight > window.innerHeight - 16 && anchor.top > pickerHeight + 24

    return {
      left: `${left}px`,
      top: openAbove ? `${anchor.top - 8}px` : `${belowTop}px`,
      transform: openAbove ? 'translateY(-100%)' : 'none',
    }
  }

  function setToolPopoverVisible(tool, value) {
    const key = String(tool?.key || '').trim()
    if (!key) return
    activeToolPopoverKey.value = value ? key : ''
    if (!value) {
      activeToolPopoverAnchor.value = null
    }
  }

  function closeToolPopover() {
    activeToolPopoverKey.value = ''
    activeToolPopoverAnchor.value = null
  }

  function getToolPopoverAnchor() {
    const element = getToolPopoverAnchorElement()
    return element?.getBoundingClientRect?.() || null
  }

  function getToolPopoverAnchorElement() {
    return activeToolPopoverAnchor.value?.closest?.('.composer-tool') || activeToolPopoverAnchor.value
  }

  async function handleToolPopoverSelect(value) {
    const tool = activeToolPopover.value?.tool
    const context = buildToolContext(tool)
    closeToolPopover()
    if (typeof tool?.onSelect === 'function') {
      await tool.onSelect({
        ...context,
        value,
      })
      return
    }
    if (typeof tool?.popoverSelect === 'function') {
      await tool.popoverSelect({
        ...context,
        value,
      })
      return
    }
    await insertComposerText(String(value || ''))
  }

  return {
    attachmentInput,
    activeAutocomplete,
    activeToolPopover,
    autocompleteActiveIndex,
    composerExtensionNotices,
    composerHeight,
    composerInlineStyle,
    composerSecondaryActions,
    composerStatusItems,
    composerTextarea,
    composerTools,
    handleAttachmentSelected,
    handleComposerSecondaryAction,
    handleEditorInteraction,
    handleEditorKeydown,
    handleAutocompleteHighlight,
    handleAutocompleteSelect,
    handleImageSelected,
    handleToolPopoverSelect,
    imageInput,
    insertComposerText,
    isPhoneOverlay,
    isPhoneViewport,
    previewError,
    previewHtml,
    previewLoading,
    requestPreview,
    resizing,
    showBackdrop,
    showAutocomplete,
    showPreview,
    startResize,
    syncInlineSuggestions,
    togglePreview,
    uploadNotice,
    uploadNoticeTone,
    uploading,
    applyComposerTool,
    clearRuntimeState,
    buildExtensionContext,
  }
}
