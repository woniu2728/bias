import { buildDiscussionHeroColorStyle, extendForum, forumApi, getUiCopy, registerResourceNormalizer } from '@bias/forum'
import DiscussionTagLabels from './DiscussionTagLabels.vue'
import DiscussionTaggedPostItem from './DiscussionTaggedPostItem.vue'
import DiscussionComposerTagFields from './DiscussionComposerTagFields.vue'
import DiscussionSidebarTagsSection from './DiscussionSidebarTagsSection.vue'
import TagDiscussionModal from './TagDiscussionModal.vue'
import { buildTagPath, flattenTags, normalizeTag, unwrapTagList } from './tagUtils.js'

export const extend = [
  extendForum(registerTagsForum),
]

function registerTagsForum(forum) {
  registerResourceNormalizer('tags', normalizeTag)
  registerResourceNormalizer('tag', normalizeTag)

  forum.postType('discussionTagged', {
    label: '讨论标签变更',
    component: DiscussionTaggedPostItem,
    order: 50,
  })

  forum.navItem({
    key: 'tags',
    moduleId: 'tags',
    to: '/tags',
    icon: 'fas fa-tags',
    label: '全部标签',
    description: '按标签浏览论坛主题。',
    section: 'primary',
    order: 30,
    surfaces: ['primary-nav', 'mobile-drawer'],
    isActive: ({ route }) => route?.name === 'tags' || route?.name === 'tag-detail',
  })

  forum.sidebarSection({
    key: 'tags',
    moduleId: 'tags',
    order: 30,
    surfaces: ['discussion-sidebar'],
    isVisible: context => getTagsSidebarContextData(context).flatTags.length > 0,
    resolve: context => {
      const sidebarContext = getTagsSidebarContextData(context)
      return {
        component: DiscussionSidebarTagsSection,
        componentProps: {
          currentTag: sidebarContext.currentTag,
          currentTagSlug: sidebarContext.currentTagSlug,
          flatTags: sidebarContext.flatTags,
          isTagsPage: context.route?.name === 'tags',
          normalizedTags: sidebarContext.normalizedTags,
          tagsIndexIcon: 'fas fa-tags',
          tagsIndexPath: '/tags',
        },
      }
    },
  })

  forum.discussionListContext({
    key: 'tag-filter',
    moduleId: 'tags',
    order: 10,
    surfaces: ['discussion-list'],
    isVisible: ({ route, isFollowingPage }) => route?.name === 'tag-detail' && !isFollowingPage,
    resolve: ({ route }) => {
      const currentTagSlug = String(route?.params?.slug || '').trim()
      return {
        currentTagSlug,
        async loadResources({ resourceStore }) {
          const tagsResponse = await forumApi.get('/tags', {
            params: {
              include_children: true,
            },
          })
          let currentTagResponse = null
          if (currentTagSlug) {
            try {
              currentTagResponse = await forumApi.get(`/tags/slug/${currentTagSlug}`)
            } catch (error) {
              console.error('加载标签详情失败:', error)
            }
          }
          const tags = unwrapTagList(tagsResponse).map(normalizeTag)
          resourceStore.upsertMany('tags', tags)
          const currentTag = currentTagResponse
            ? resourceStore.upsert('tags', normalizeTag(currentTagResponse))
            : null
          const normalizedTags = unwrapTagList(tagsResponse).map(normalizeTag)
          return {
            contextData: buildTagsSidebarContextData({
              currentTag,
              currentTagSlug,
              tags: normalizedTags,
            }),
            subject: currentTag || null,
            subjectKey: currentTagSlug,
          }
        },
      }
    },
  })

  forum.discussionListContext({
    key: 'tag-sidebar-resources',
    moduleId: 'tags',
    order: 20,
    surfaces: ['discussion-list'],
    isVisible: ({ route }) => route?.name !== 'tag-detail',
    resolve: () => ({
      async loadResources({ resourceStore }) {
        const response = await forumApi.get('/tags', {
          params: {
            include_children: true,
          },
        })
        const normalizedTags = unwrapTagList(response).map(normalizeTag)
        resourceStore.upsertMany('tags', normalizedTags)
        return {
          contextData: buildTagsSidebarContextData({
            tags: normalizedTags,
          }),
        }
      },
    }),
  })

  forum.discussionListRequest({
    key: 'tag-filter',
    moduleId: 'tags',
    order: 10,
    surfaces: ['discussion-list-request'],
    isVisible: ({ contexts }) => Array.isArray(contexts) && contexts.some(item => item?.currentTagSlug),
    resolve: ({ contexts }) => ({
      apply({ params }) {
        const tagContext = contexts.find(item => item?.currentTagSlug)
        if (!tagContext?.currentTagSlug) {
          return params
        }
        return {
          ...params,
          tag: tagContext.currentTagSlug,
        }
      },
    }),
  })

  forum.discussionListHero({
    key: 'tag-detail-hero',
    moduleId: 'tags',
    order: 10,
    surfaces: ['discussion-list-hero'],
    isVisible: ({ contextSubject }) => Boolean(contextSubject),
    resolve: ({ contextSubject }) => ({
      pill: contextSubject.name,
      title: contextSubject.name,
      description: contextSubject.description || getUiCopy({
        surface: 'discussion-list-tag-hero-description',
        subjectName: contextSubject.name,
      })?.text || '这个标签下的讨论会集中显示在这里。',
      bulletColor: contextSubject.color,
      style: {
        '--discussion-list-hero-color': contextSubject.color || 'var(--forum-primary-color)',
      },
    }),
  })

  forum.discussionPresentation({
    key: 'discussion-list-tags',
    moduleId: 'tags',
    order: 10,
    surfaces: ['discussion-list-item-meta'],
    isVisible: ({ discussion }) => Array.isArray(discussion?.tags) && discussion.tags.length > 0,
    resolve: ({ discussion }) => ({
      component: DiscussionTagLabels,
      componentProps: {
        tags: discussion.tags,
        size: 'sm',
        maxWidth: '160px',
      },
      className: 'item-tags',
    }),
  })

  forum.discussionAction({
    key: 'edit-tags',
    moduleId: 'tags',
    order: 35,
    surfaces: ['discussion-menu'],
    isVisible: ({ canEditDiscussion, discussion }) => Boolean(canEditDiscussion && discussion?.id),
    resolve: () => ({
      key: 'edit-tags',
      label: getUiCopy({
        surface: 'discussion-action-edit-tags-label',
      })?.text || '编辑标签',
      icon: 'fas fa-tags',
      description: getUiCopy({
        surface: 'discussion-action-edit-tags-description',
      })?.text || '调整当前讨论归属的标签。',
      order: 35,
    }),
  })

  forum.discussionActionHandler({
    key: 'edit-tags',
    moduleId: 'tags',
    order: 10,
    handle: handleEditDiscussionTags,
  })

  forum.discussionPresentation({
    key: 'discussion-hero-tags',
    moduleId: 'tags',
    order: 5,
    surfaces: ['discussion-hero'],
    isVisible: ({ discussion }) => Array.isArray(discussion?.tags) && discussion.tags.length > 0,
    resolve: ({ discussion }) => {
      const primaryTag = discussion.tags.find(tag => tag?.color)
      return {
        component: DiscussionTagLabels,
        componentProps: {
          tags: discussion.tags,
          size: 'md',
          maxWidth: '220px',
        },
        heroStyle: primaryTag?.color ? buildDiscussionHeroColorStyle(primaryTag.color) : {},
      }
    },
  })

  forum.emptyState({
    key: 'tags-page-empty',
    moduleId: 'tags',
    order: 50,
    surfaces: ['tags-page-empty'],
    isVisible: ({ tags }) => Array.isArray(tags) && tags.length === 0,
    resolve: () => ({
      text: '暂无标签',
    }),
  })

  forum.emptyState({
    key: 'discussion-list-tag-empty',
    moduleId: 'tags',
    order: 40,
    surfaces: ['discussion-list-empty'],
    isVisible: ({ contextSubject }) => Boolean(contextSubject),
    resolve: () => ({
      text: '这个标签下还没有讨论。',
    }),
  })

  forum.emptyState({
    key: 'tag-last-discussion-empty',
    moduleId: 'tags',
    order: 60,
    surfaces: ['tag-last-discussion-empty'],
    isVisible: ({ tag }) => !tag?.last_posted_discussion,
    resolve: () => ({
      text: '暂无讨论',
    }),
  })

  forum.stateBlock({
    key: 'tags-page-loading',
    moduleId: 'tags',
    order: 40,
    surfaces: ['tags-page-loading'],
    isVisible: ({ loading }) => Boolean(loading),
    resolve: () => ({
      text: '加载中...',
    }),
  })

  forum.uiCopy({
    key: 'discussion-composer-primary-tag-placeholder',
    moduleId: 'tags',
    order: 30,
    surfaces: ['discussion-composer-primary-tag-placeholder'],
    resolve: ({ loadingTags, hasStartableTags }) => ({
      text: loadingTags ? '加载标签中...' : (hasStartableTags ? '选择主标签' : '暂无可发帖标签'),
    }),
  })

  forum.uiCopy({
    key: 'discussion-action-edit-tags-label',
    moduleId: 'tags',
    order: 479,
    surfaces: ['discussion-action-edit-tags-label'],
    resolve: () => ({
      text: '编辑标签',
    }),
  })

  forum.uiCopy({
    key: 'discussion-action-edit-tags-description',
    moduleId: 'tags',
    order: 479,
    surfaces: ['discussion-action-edit-tags-description'],
    resolve: () => ({
      text: '调整当前讨论归属的标签。',
    }),
  })

  forum.uiCopy({
    key: 'tag-discussion-title',
    moduleId: 'tags',
    order: 840,
    surfaces: ['tag-discussion-title'],
    resolve: () => ({
      text: '编辑讨论标签',
    }),
  })

  forum.uiCopy({
    key: 'tag-discussion-description',
    moduleId: 'tags',
    order: 850,
    surfaces: ['tag-discussion-description'],
    resolve: () => ({
      text: '调整这个讨论归属的主标签和次标签。',
    }),
  })

  forum.uiCopy({
    key: 'tag-discussion-primary-label',
    moduleId: 'tags',
    order: 860,
    surfaces: ['tag-discussion-primary-label'],
    resolve: () => ({
      text: '主标签',
    }),
  })

  forum.uiCopy({
    key: 'tag-discussion-secondary-label',
    moduleId: 'tags',
    order: 870,
    surfaces: ['tag-discussion-secondary-label'],
    resolve: () => ({
      text: '次标签',
    }),
  })

  forum.uiCopy({
    key: 'tag-discussion-primary-placeholder',
    moduleId: 'tags',
    order: 880,
    surfaces: ['tag-discussion-primary-placeholder'],
    resolve: ({ loading, hasTags }) => ({
      text: loading ? '加载标签中...' : (hasTags ? '选择主标签' : '暂无可用主标签'),
    }),
  })

  forum.uiCopy({
    key: 'tag-discussion-secondary-placeholder',
    moduleId: 'tags',
    order: 890,
    surfaces: ['tag-discussion-secondary-placeholder'],
    resolve: ({ hasSecondaryOptions }) => ({
      text: hasSecondaryOptions ? '不选择次标签' : '无可用次标签',
    }),
  })

  forum.uiCopy({
    key: 'tag-discussion-secondary-help',
    moduleId: 'tags',
    order: 900,
    surfaces: ['tag-discussion-secondary-help'],
    resolve: () => ({
      text: '次标签必须隶属于当前主标签。',
    }),
  })

  forum.uiCopy({
    key: 'tag-discussion-submit-button',
    moduleId: 'tags',
    order: 910,
    surfaces: ['tag-discussion-submit-button'],
    resolve: ({ submitting }) => ({
      text: submitting ? '保存中...' : '保存标签',
    }),
  })

  forum.uiCopy({
    key: 'discussion-composer-secondary-tag-placeholder',
    moduleId: 'tags',
    order: 40,
    surfaces: ['discussion-composer-secondary-tag-placeholder'],
    resolve: ({ hasSecondaryOptions }) => ({
      text: hasSecondaryOptions ? '选择次标签（可选）' : '无可用次标签',
    }),
  })

  forum.uiCopy({
    key: 'search-modal-popular-tags-title',
    moduleId: 'tags',
    order: 476,
    surfaces: ['search-modal-popular-tags-title'],
    resolve: () => ({
      text: '热门标签',
    }),
  })

  forum.uiCopy({
    key: 'search-modal-tag-subtitle',
    moduleId: 'tags',
    order: 476,
    surfaces: ['search-modal-tag-subtitle'],
    resolve: ({ count }) => ({
      text: `${Number(count || 0)} 条讨论`,
    }),
  })

  forum.searchModalSection({
    key: 'popular-tags',
    moduleId: 'tags',
    order: 20,
    surfaces: ['search-modal-empty'],
    async load({ modalStore, resourceStore, router }) {
      const response = await forumApi.get('/tags/popular', {
        params: {
          limit: 6,
        },
      })
      const tagIds = resourceStore.upsertMany('tags', unwrapTagList(response).map(normalizeTag))
        .map(item => item.id)
      const tags = resourceStore.list('tags', tagIds)

      return {
        key: 'popular-tags',
        title: getUiCopy({
          surface: 'search-modal-popular-tags-title',
        })?.text || '热门标签',
        items: tags.map(tag => ({
          key: `tag-${tag.id}`,
          kind: 'popular-tag',
          icon: 'fas fa-tags',
          title: tag.name,
          subtitle: getUiCopy({
            surface: 'search-modal-tag-subtitle',
            count: Number(tag.discussion_count || 0),
          })?.text || `${Number(tag.discussion_count || 0)} 条讨论`,
          action: () => {
            modalStore.dismiss()
            router.push(buildTagPath(tag))
          },
        })),
      }
    },
  })

  forum.uiCopy({
    key: 'tags-page-hero-title',
    moduleId: 'tags',
    order: 479,
    surfaces: ['tags-page-hero-title'],
    resolve: () => ({
      text: '全部标签',
    }),
  })

  forum.uiCopy({
    key: 'tags-page-hero-description',
    moduleId: 'tags',
    order: 479,
    surfaces: ['tags-page-hero-description'],
    resolve: ({ tagCount }) => ({
      text: Number(tagCount || 0) > 0
        ? `浏览 ${tagCount} 个论坛标签，按主题发现相关讨论。`
        : '浏览论坛标签，按主题发现相关讨论。',
    }),
  })

  forum.uiCopy({
    key: 'discussion-list-tag-hero-description',
    moduleId: 'tags',
    order: 479,
    surfaces: ['discussion-list-tag-hero-description'],
    resolve: () => ({
      text: '这个标签下的讨论会集中显示在这里。',
    }),
  })

  forum.uiCopy({
    key: 'discussion-list-sidebar-tags-link',
    moduleId: 'tags',
    order: 479,
    surfaces: ['discussion-list-sidebar-tags-link'],
    resolve: () => ({
      text: '标签',
    }),
  })

  forum.uiCopy({
    key: 'discussion-list-sidebar-more-tags-link',
    moduleId: 'tags',
    order: 479,
    surfaces: ['discussion-list-sidebar-more-tags-link'],
    resolve: () => ({
      text: '更多标签',
    }),
  })

  forum.uiCopy({
    key: 'discussion-event-tagged-label',
    moduleId: 'tags',
    order: 479,
    surfaces: ['discussion-event-tagged-label'],
    resolve: () => ({
      text: '更新了讨论标签',
    }),
  })

  forum.uiCopy({
    key: 'discussion-event-tagged-added-prefix',
    moduleId: 'tags',
    order: 479,
    surfaces: ['discussion-event-tagged-added-prefix'],
    resolve: () => ({
      text: '新增',
    }),
  })

  forum.uiCopy({
    key: 'discussion-event-tagged-removed-prefix',
    moduleId: 'tags',
    order: 479,
    surfaces: ['discussion-event-tagged-removed-prefix'],
    resolve: () => ({
      text: '移除',
    }),
  })

  forum.uiCopy({
    key: 'tags-mobile-page-title',
    moduleId: 'tags',
    order: 300,
    surfaces: ['header-mobile-page-title'],
    isVisible: ({ routeName }) => routeName === 'tags' || routeName === 'tag-detail',
    resolve: ({ routeName }) => ({
      text: routeName === 'tag-detail' ? '标签讨论' : '标签',
    }),
  })

  forum.uiCopy({
    key: 'mobile-drawer-all-tags',
    moduleId: 'tags',
    order: 530,
    surfaces: ['mobile-drawer-all-tags'],
    resolve: () => ({
      text: '全部标签',
    }),
  })

  forum.composerField({
    key: 'discussion-tag-fields',
    moduleId: 'tags',
    order: 20,
    isVisible: ({ type }) => type === 'discussion',
    resolve: context => ({
      component: DiscussionComposerTagFields,
      componentProps: {
        closeComposer: context.closeComposer,
        current: context.current,
        isSuspended: Boolean(context.isSuspended),
        requestId: context.current?.requestId,
        state: getTagsComposerState(context),
        submitting: Boolean(context.submitting),
        updateState: value => context.updateExtensionState?.('tags', value),
      },
      statusText: getTagsComposerState(context).selectedTagLabel || '',
    }),
  })

  forum.composerInitialState({
    key: 'discussion-edit-tags',
    moduleId: 'tags',
    order: 20,
    isVisible: ({ submitKind, discussion }) => submitKind === 'edit-discussion' && Array.isArray(discussion?.tags),
    contribute({ discussion }) {
      const currentTags = flattenTags(discussion.tags || [])
      const primaryTag = currentTags.find(tag => !tag.parent_id)
      const secondaryTag = currentTags.find(tag => tag.parent_id)
      const selectedTagIds = [primaryTag?.id, secondaryTag?.id]
        .filter(Boolean)
        .map(value => parseInt(value, 10))
        .filter(Number.isInteger)
      return {
        extensions: {
          tags: {
            primaryTagId: primaryTag?.id ? String(primaryTag.id) : '',
            secondaryTagId: secondaryTag?.id ? String(secondaryTag.id) : '',
            selectedTagIds,
          },
        },
      }
    },
  })

  forum.composerPayloadContributor({
    key: 'discussion-tags-relationship',
    moduleId: 'tags',
    order: 20,
    isVisible: ({ type }) => type === 'discussion',
    contribute({ payload, extensionState }) {
      const selectedTagIds = getTagsComposerState({ extensionState }).selectedTagIds || []
      return {
        ...payload,
        data: {
          ...payload.data,
          relationships: {
            ...(payload.data?.relationships || {}),
            tags: {
              data: selectedTagIds.map(tagId => ({
                type: 'tag',
                id: String(tagId),
              })),
            },
          },
        },
      }
    },
  })

  forum.composerNotice({
    key: 'discussion-tag-permission',
    moduleId: 'tags',
    order: 30,
    isVisible: context => {
      const state = getTagsComposerState(context)
      return context.type === 'discussion' && !state.loadingTags && Number(state.availablePrimaryTagCount || 0) <= 0
    },
    resolve: () => ({
      label: '标签',
      tone: 'warning',
      message: '当前没有可发帖的标签，请联系管理员开放标签权限。',
    }),
  })

  forum.composerNotice({
    key: 'discussion-tag-selection',
    moduleId: 'tags',
    order: 40,
    isVisible: context => {
      const state = getTagsComposerState(context)
      return context.type === 'discussion' && Number(state.availablePrimaryTagCount || 0) > 0 && !state.primaryTagId
    },
    resolve: () => ({
      label: '标签',
      tone: 'info',
      message: '先选择主标签，再发布讨论。',
    }),
  })

  forum.composerSubmitGuard({
    key: 'discussion-primary-tag',
    moduleId: 'tags',
    order: 30,
    isVisible: ({ type }) => type === 'discussion',
    check: context => {
      const state = getTagsComposerState(context)
      if (state.loadingTags) {
        return {
          tone: 'error',
          message: '标签仍在加载中，请稍后再发布。',
        }
      }

      if (Number(state.availablePrimaryTagCount || 0) <= 0) {
        return {
          tone: 'error',
          message: '当前没有可用主标签，暂时无法发布讨论。',
        }
      }

      if (state.primaryTagId) return null
      return {
        tone: 'error',
        message: '请选择主标签后再发布讨论。',
      }
    },
  })

  forum.composerStatusItem({
    key: 'discussion-selected-tag',
    moduleId: 'tags',
    order: 10,
    isVisible: context => context.type === 'discussion' && Boolean(getTagsComposerState(context).selectedTagLabel) && !context.minimized,
    resolve: context => ({
      label: '标签',
      value: getTagsComposerState(context).selectedTagLabel,
    }),
  })
}

function getTagsComposerState(context = {}) {
  return context.extensionState?.tags || {}
}

function buildTagsSidebarContextData({
  currentTag = null,
  currentTagSlug = '',
  tags = [],
} = {}) {
  const normalizedTags = unwrapTagList(tags).map(normalizeTag)
  return {
    currentTag,
    currentTagSlug,
    flatTags: flattenTags(normalizedTags),
    normalizedTags,
    startDiscussionExtensionState: currentTag?.id
      ? {
          tags: {
            requestedTagId: String(currentTag.id),
          },
        }
      : {},
  }
}

function getTagsSidebarContextData(context = {}) {
  const data = context.discussionListContextData || {}
  return data['tag-filter'] || data['tag-sidebar-resources'] || buildTagsSidebarContextData()
}

async function handleEditDiscussionTags({
  discussion,
  modalStore,
  patchDiscussion,
  showActionError,
}) {
  if (!discussion?.id || !modalStore?.show) {
    return
  }

  try {
    const result = await modalStore.show(
      TagDiscussionModal,
      { discussion },
      { size: 'small' }
    )
    if (!result?.updated || !result.discussion) {
      return
    }
    patchDiscussion?.(result.discussion)
  } catch (error) {
    console.error('更新讨论标签失败:', error)
    await showActionError?.('编辑标签', error)
  }
}
