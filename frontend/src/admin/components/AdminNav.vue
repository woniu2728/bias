<template>
  <nav class="AdminNav" :class="{ 'is-mobile-open': mobileOpen }">
    <div v-if="mobileOpen" class="AdminNav-backdrop" @click="$emit('close')"></div>
    <div class="AdminNav-panel">
      <div class="AdminNav-mobileHeader">
        <strong>管理后台</strong>
        <button type="button" class="AdminNav-close" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="AdminNav-section">
        <ForumNavList
          :sections="coreSections"
          root-class="AdminNav-sections"
          section-title-class="AdminNav-title"
          section-list-class="AdminNav-list"
          item-wrapper-class="AdminNav-itemWrap"
          item-class="AdminNav-item"
          item-description-class="AdminNav-description"
          item-badge-class="AdminNav-badge"
          @select="$emit('close')"
        />
      </div>

      <div v-if="hasExtensionSection" class="AdminNav-section AdminNav-section--extensions">
        <div class="AdminNav-search">
          <label class="sr-only" for="admin-extension-search">搜索扩展</label>
          <span class="AdminNav-searchIcon" aria-hidden="true">
            <i class="fas fa-search"></i>
          </span>
          <input
            id="admin-extension-search"
            v-model.trim="extensionQuery"
            type="search"
            class="AdminNav-searchInput"
            placeholder="搜索扩展"
          />
        </div>
        <ForumNavList
          v-if="extensionSections.length"
          :sections="extensionSections"
          root-class="AdminNav-sections"
          section-title-class="AdminNav-title"
          section-list-class="AdminNav-list"
          item-wrapper-class="AdminNav-itemWrap"
          item-class="AdminNav-item"
          item-description-class="AdminNav-description"
          item-badge-class="AdminNav-badge"
          @select="$emit('close')"
        />
        <p v-else class="AdminNav-empty">没有匹配的扩展</p>
      </div>

      <div class="AdminNav-mobileFooter">
        <a href="/" class="AdminNav-item" @click="$emit('close')">
          <i class="fas fa-arrow-left"></i>
          <span>返回论坛</span>
        </a>
        <button type="button" class="AdminNav-item AdminNav-item--danger" @click="handleLogout">
          <i class="fas fa-sign-out-alt"></i>
          <span>登出</span>
        </button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import ForumNavList from '@/components/forum/ForumNavList.vue'
import { useAuthStore } from '@bias/users'
import { getAdminNavSections, isAdminPathActive } from '../navigation'

defineProps({
  mobileOpen: {
    type: Boolean,
    default: false
  }
})

defineEmits(['close'])

const route = useRoute()
const authStore = useAuthStore()
const extensionQuery = ref('')
const navSections = computed(() => getAdminNavSections()
  .map(section => ({
    ...section,
    items: filterSectionItems(section).map(item => ({
      ...item,
      to: item.path,
      active: isActive(item.path),
    }))
  }))
  .filter(section => section.items.length))
const coreSections = computed(() => navSections.value.filter(section => section.key !== 'extensions'))
const extensionSections = computed(() => navSections.value.filter(section => section.key === 'extensions'))
const hasExtensionSection = computed(() => getAdminNavSections().some(section => section.key === 'extensions'))

function filterSectionItems(section) {
  const items = Array.isArray(section?.items) ? section.items : []
  const query = extensionQuery.value.trim().toLowerCase()

  if (!query || section.key !== 'extensions') {
    return items
  }

  return items.filter((item) => {
    const haystack = [
      item.label,
      item.description,
      item.path,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return haystack.includes(query)
  })
}

function isActive(path) {
  return isAdminPathActive(route.path, path)
}

function handleLogout() {
  authStore.logout()
  window.location.href = '/login'
}
</script>

<style scoped>
.AdminNav {
  width: 250px;
  flex-shrink: 0;
  height: 100%;
}

.AdminNav-panel {
  position: relative;
  top: auto;
  height: 100%;
  overflow-y: auto;
  padding: 10px 0 40px;
  background: #fff;
  box-shadow: 0 6px 18px rgba(48, 67, 91, 0.12);
  scrollbar-width: thin;
  scrollbar-color: rgba(128, 142, 158, 0.9) transparent;
}

.AdminNav-panel::-webkit-scrollbar {
  width: 12px;
}

.AdminNav-panel::-webkit-scrollbar-track {
  background: transparent;
}

.AdminNav-panel::-webkit-scrollbar-thumb {
  border: 3px solid transparent;
  border-radius: 999px;
  background: rgba(128, 142, 158, 0.85);
  background-clip: padding-box;
}

.AdminNav-mobileHeader,
.AdminNav-backdrop,
.AdminNav-mobileFooter {
  display: none;
}

.AdminNav-section {
  margin-bottom: 26px;
}

.AdminNav-section--extensions {
  margin-bottom: 0;
}

.AdminNav-search {
  position: relative;
  padding: 0 10px;
  margin: 2px 0 18px;
}

.AdminNav-searchIcon {
  position: absolute;
  top: 50%;
  left: 22px;
  transform: translateY(-50%);
  color: #6f86a2;
  font-size: 14px;
  pointer-events: none;
}

.AdminNav-searchInput {
  width: 100%;
  min-height: 36px;
  padding: 0 12px 0 36px;
  border: 0;
  border-radius: 999px;
  background: #e8eff7;
  color: #3b536f;
  font-size: 13px;
  transition: background-color 0.18s ease, box-shadow 0.18s ease;
}

.AdminNav-searchInput::placeholder {
  color: #7f93aa;
}

.AdminNav-searchInput:focus {
  outline: none;
  background: #dfe9f5;
  box-shadow: inset 0 0 0 1px rgba(113, 136, 165, 0.2);
}

.AdminNav-sections {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.AdminNav :deep(.AdminNav-title) {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: #7f8c99;
  margin: 0 0 8px;
  padding: 0 15px;
  letter-spacing: 0.04em;
}

.AdminNav :deep(.AdminNav-list) {
  display: flex;
  flex-direction: column;
  gap: 0;
  list-style: none;
  padding: 0;
  margin: 0;
}

.AdminNav :deep(.AdminNav-itemWrap) {
  list-style: none;
  margin: 0;
}

.AdminNav :deep(.AdminNav-item) {
  display: flex;
  align-items: center;
  gap: 9px;
  position: relative;
  min-height: 44px;
  padding: 10px 10px 10px 15px;
  color: #2f3d4d;
  text-decoration: none;
  border-radius: 0;
  font-size: 14px;
  font-weight: 400;
  transition: background-color 0.18s ease, color 0.18s ease;
}

.AdminNav :deep(.AdminNav-item i) {
  width: 25px;
  text-align: center;
  font-size: 13px;
  flex-shrink: 0;
  color: #22384f;
}

.AdminNav-section--extensions :deep(.AdminNav-item i) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 7px;
  background: var(--admin-extension-icon-bg, #eef2f7);
  color: var(--admin-extension-icon-color, #5f748b);
  font-size: 13px;
}

.AdminNav :deep(.AdminNav-item span) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.AdminNav :deep(.AdminNav-item:hover) {
  background: #eef3f8;
  color: #2f3d4d;
  text-decoration: none;
}

.AdminNav :deep(.AdminNav-item.active) {
  background: #5c7698;
  color: #fff;
  box-shadow: none;
}

.AdminNav :deep(.AdminNav-item.active:hover) {
  background: #5c7698;
}

.AdminNav :deep(.AdminNav-item.active span),
.AdminNav :deep(.AdminNav-item.active i) {
  font-weight: 700;
  color: inherit;
}

.AdminNav-section--extensions :deep(.AdminNav-item.active i) {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}

.AdminNav :deep(.AdminNav-description) {
  display: none;
}

.AdminNav :deep(.AdminNav-badge) {
  margin-left: auto;
  width: 10px;
  min-width: 10px;
  height: 10px;
  padding: 0;
  border-radius: 999px;
  background: #34c759;
  color: transparent;
  box-shadow: none;
}

.AdminNav-item--danger {
  border: 0;
  width: 100%;
  background: transparent;
  color: #b34c45;
  cursor: pointer;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 960px) {
  .AdminNav {
    width: 100%;
    height: auto;
  }

  .AdminNav-panel {
    position: static;
    top: auto;
    height: auto;
    box-shadow: none;
  }
}

@media (max-width: 768px) {
  .AdminNav {
    width: 0;
  }

  .AdminNav-backdrop {
    display: block;
    position: fixed;
    inset: 56px 0 0;
    background: rgba(24, 38, 54, 0.38);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease;
    z-index: 119;
  }

  .AdminNav-panel {
    position: fixed;
    top: 56px;
    left: 0;
    bottom: 0;
    width: min(320px, calc(100vw - 44px));
    max-height: none;
    padding: 14px 14px 20px;
    background: var(--forum-bg-elevated);
    box-shadow: var(--forum-shadow-lg);
    transform: translateX(calc(-100% - 12px));
    transition: transform 0.22s ease;
    z-index: 120;
    overflow-y: auto;
  }

  .AdminNav.is-mobile-open .AdminNav-backdrop {
    opacity: 1;
    pointer-events: auto;
  }

  .AdminNav.is-mobile-open .AdminNav-panel {
    transform: translateX(0);
  }

  .AdminNav-mobileHeader {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 14px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--forum-border-soft);
    color: #31465d;
    font-size: 15px;
  }

  .AdminNav-close {
    width: 36px;
    height: 36px;
    padding: 0;
    border: 0;
    border-radius: 999px;
    background: var(--forum-bg-subtle);
    color: #607285;
  }

  .AdminNav-section {
    margin-bottom: 18px;
  }

  .AdminNav-search {
    padding: 0 4px;
    margin-bottom: 12px;
  }

  .AdminNav-title {
    padding: 0 4px;
    margin-bottom: 8px;
    font-size: 11px;
  }

  .AdminNav-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .AdminNav-item {
    min-height: 44px;
    padding: 0 14px;
    border-radius: 12px;
    background: transparent;
  }

  .AdminNav-item.active {
    box-shadow: none;
  }

  .AdminNav-mobileFooter {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 14px;
    border-top: 1px solid var(--forum-border-soft);
  }
}
</style>
