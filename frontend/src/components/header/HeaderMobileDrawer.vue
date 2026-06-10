<template>
  <transition name="mobile-drawer-fade">
    <div
      v-if="showMobileDrawer"
      class="mobile-drawer-backdrop"
      @click="$emit('close')"
    ></div>
  </transition>

  <aside class="mobile-drawer" :class="{ 'is-open': showMobileDrawer }">
    <div class="mobile-drawer-header">
      <router-link
        to="/"
        class="mobile-drawer-brand"
        @click="$emit('close')"
      >
        <img
          v-if="forumStore.settings.logo_url"
          :src="forumStore.settings.logo_url"
          :alt="forumStore.settings.forum_title"
          class="mobile-drawer-logo"
        />
        <span v-else>{{ forumStore.settings.forum_title }}</span>
      </router-link>
      <button
        type="button"
        class="mobile-drawer-close"
        :aria-label="closeLabelText"
        @click="$emit('close')"
      >
        <i class="fas fa-times"></i>
      </button>
    </div>

    <div v-if="actionItems.length" class="mobile-drawer-section">
      <component
        :is="item.to ? 'router-link' : item.href ? 'a' : 'button'"
        v-for="item in actionItems"
        :key="item.key"
        v-bind="item.to ? { to: item.to } : item.href ? { href: item.href } : { type: 'button' }"
        class="mobile-drawer-action"
        :class="[item.className, { active: item.active, 'mobile-drawer-action--primary': item.tone === 'primary' }]"
        @click="$emit('item-click', item, $event)"
      >
        <i v-if="item.icon" :class="item.icon"></i>
        <span>{{ item.label }}</span>
      </component>
    </div>

    <nav class="mobile-drawer-nav">
      <div class="mobile-drawer-nav-section">
        <component
          :is="item.to ? 'router-link' : item.href ? 'a' : 'button'"
          v-for="item in mobilePrimaryNavItems"
          :key="item.key"
          v-bind="item.to ? { to: item.to } : item.href ? { href: item.href } : { type: 'button' }"
          class="mobile-drawer-link"
          :class="{ active: item.active }"
          @click="$emit('close')"
        >
          <i v-if="item.icon" :class="item.icon"></i>
          <span>{{ item.label }}</span>
          <span v-if="item.badge" class="mobile-drawer-badge">
            {{ item.badge }}
          </span>
        </component>
      </div>

      <div v-if="authStore.isAuthenticated && authStore.user" class="mobile-drawer-nav-section">
        <h4 class="mobile-drawer-title">{{ profileSectionTitleText }}</h4>
        <component
          :is="item.to ? 'router-link' : item.href ? 'a' : 'button'"
          v-for="item in personalItems"
          :key="item.key"
          v-bind="item.to ? { to: item.to } : item.href ? { href: item.href } : { type: 'button' }"
          class="mobile-drawer-link"
          :class="{ active: item.active, 'mobile-drawer-link--danger': item.tone === 'danger' }"
          @click="$emit('item-click', item, $event)"
        >
          <i v-if="item.icon" :class="item.icon"></i>
          <span>{{ item.label }}</span>
          <span v-if="item.badge" class="mobile-drawer-badge">
            {{ item.badge }}
          </span>
        </component>
      </div>
    </nav>

    <div v-if="authStore.isAuthenticated && authStore.user" class="mobile-drawer-user">
      <component
        :is="item.component"
        v-for="item in userCardItems"
        :key="item.key"
        v-bind="item.componentProps || {}"
      />
      <component
        :is="item.to ? 'router-link' : item.href ? 'a' : 'button'"
        v-for="item in userItems"
        :key="item.key"
        v-bind="item.to ? { to: item.to } : item.href ? { href: item.href } : { type: 'button' }"
        class="mobile-drawer-link"
        :class="{ active: item.active, 'mobile-drawer-link--danger': item.tone === 'danger' }"
        @click="$emit('item-click', item, $event)"
      >
        <i v-if="item.icon" :class="item.icon"></i>
        <span>{{ item.label }}</span>
      </component>
    </div>

    <div v-else class="mobile-drawer-auth">
      <button
        v-for="item in guestItems"
        :key="item.key"
        type="button"
        :class="item.tone === 'primary' ? 'btn-signup' : 'btn-login'"
        @click="$emit('item-click', item, $event)"
      >
        {{ item.label }}
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { getForumNavItems, getUiCopy } from '@/forum/registry'

const props = defineProps({
  showMobileDrawer: {
    type: Boolean,
    default: false
  },
  authStore: {
    type: Object,
    required: true
  },
  forumStore: {
    type: Object,
    required: true
  },
  isMobileNavActive: {
    type: Function,
    required: true
  },
  actionItems: {
    type: Array,
    default: () => []
  },
  userCardItems: {
    type: Array,
    default: () => []
  },
  guestItems: {
    type: Array,
    default: () => []
  },
  personalItems: {
    type: Array,
    default: () => []
  },
  userItems: {
    type: Array,
    default: () => []
  }
})

const closeLabelText = computed(() => getUiCopy({
  surface: 'mobile-drawer-close-label',
})?.text || '关闭导航菜单')
const profileSectionTitleText = computed(() => getUiCopy({
  surface: 'mobile-drawer-profile-section-title',
})?.text || '个人')
const mobilePrimaryNavItems = computed(() => getForumNavItems({
  authStore: props.authStore,
  forumStore: props.forumStore,
  surface: 'mobile-drawer',
}).filter(item => (item.section || 'primary') === 'primary').map(item => ({
  ...item,
  active: Boolean(item.active || props.isMobileNavActive(item.key)),
})))

defineEmits([
  'close',
  'item-click',
])
</script>

<style scoped>
.mobile-drawer,
.mobile-drawer-backdrop {
  display: none;
}

.mobile-drawer-close {
  width: 40px;
  height: 40px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #62758a;
  align-items: center;
  justify-content: center;
}

.mobile-drawer {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: min(320px, calc(100vw - 44px));
  padding: 16px 14px 20px;
  background: #fff;
  box-shadow: 0 18px 40px rgba(31, 45, 61, 0.22);
  transform: translateX(calc(-100% - 12px));
  transition: transform 0.22s ease;
  z-index: 121;
  overflow-y: auto;
}

.mobile-drawer.is-open {
  transform: translateX(0);
}

.mobile-drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(27, 40, 55, 0.38);
  z-index: 120;
}

.mobile-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.mobile-drawer-brand {
  min-width: 0;
  display: flex;
  align-items: center;
  color: #31465d;
  font-size: 18px;
  font-weight: 700;
  text-decoration: none;
}

.mobile-drawer-brand:hover {
  text-decoration: none;
}

.mobile-drawer-logo {
  max-width: 168px;
  max-height: 32px;
  object-fit: contain;
}

.mobile-drawer-section,
.mobile-drawer-user,
.mobile-drawer-auth {
  padding-top: 14px;
  border-top: 1px solid #e7edf3;
}

.mobile-drawer-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.mobile-drawer-action,
.mobile-drawer-link {
  width: 100%;
  min-height: 40px;
  padding: 0 12px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
}

.mobile-drawer-action {
  background: #f4f7fa;
  color: #5d6e81;
}

.mobile-drawer-action--primary {
  background: var(--forum-accent-color);
  color: #fff;
}

.mobile-drawer-nav {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-bottom: 16px;
}

.mobile-drawer-title {
  margin: 0 0 8px;
  color: #233c59;
  font-size: 18px;
  font-weight: 700;
}

.mobile-drawer-nav-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mobile-drawer-link {
  background: transparent;
  min-height: auto;
  padding: 0;
  border-radius: 0;
  color: #426287;
  justify-content: flex-start;
  gap: 12px;
  font-size: 16px;
  font-weight: 500;
}

.mobile-drawer-link.active {
  color: var(--forum-primary-color);
}

.mobile-drawer-link i {
  width: 24px;
  text-align: center;
  font-size: 18px;
  flex-shrink: 0;
}

.mobile-drawer-link--danger {
  color: #b54b4b;
}

.mobile-drawer-badge {
  margin-left: auto;
  min-width: 22px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e86f2d;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  text-align: center;
}

.mobile-drawer-user {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mobile-drawer-auth {
  display: flex;
  gap: 10px;
}

.mobile-drawer-auth .btn-login,
.mobile-drawer-auth .btn-signup {
  flex: 1;
}

.mobile-drawer-fade-enter-active,
.mobile-drawer-fade-leave-active {
  transition: opacity 0.2s ease;
}

.mobile-drawer-fade-enter-from,
.mobile-drawer-fade-leave-to {
  opacity: 0;
}

@media (max-width: 900px) {
  .mobile-drawer,
  .mobile-drawer-backdrop {
    display: block;
  }

  .mobile-drawer-close:hover {
    background: #f4f7fa;
  }
}
</style>
