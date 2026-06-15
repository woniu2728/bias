<template>
  <div class="user-dropdown" @click="$emit('toggle')">
    <img
      v-if="authStore.user?.avatar_url"
      :src="authStore.user.avatar_url"
      :alt="authStore.user?.username"
      class="avatar avatar-image"
    />
    <div v-else class="avatar" :style="{ backgroundColor: getUserAvatarColor(authStore.user) }">
      {{ getUserInitial(authStore.user) }}
    </div>
    <span class="username">{{ authStore.user?.username }}</span>
    <i class="fas fa-caret-down"></i>

    <div v-if="showUserMenu" class="dropdown-menu" @click.stop>
      <template v-for="item in items" :key="item.key">
        <div v-if="item.separated" class="dropdown-divider"></div>
        <component
          :is="item.to ? 'router-link' : item.href ? 'a' : 'button'"
          v-bind="item.to ? { to: item.to } : item.href ? { href: item.href } : { type: 'button' }"
          class="dropdown-item"
          :class="{
            'dropdown-item--danger': item.tone === 'danger',
            'dropdown-item--active': item.active
          }"
          @click="$emit('item-click', item, $event)"
        >
          <i v-if="item.icon" :class="item.icon"></i>
          <span>{{ resolveItemValue(item.label, item) }}</span>
          <strong v-if="hasBadge(item)" class="dropdown-badge">{{ resolveItemValue(item.badge, item) }}</strong>
        </component>
      </template>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  authStore: {
    type: Object,
    required: true
  },
  showUserMenu: {
    type: Boolean,
    default: false
  },
  items: {
    type: Array,
    default: () => []
  },
  getUserAvatarColor: {
    type: Function,
    required: true
  },
  getUserInitial: {
    type: Function,
    required: true
  }
})

defineEmits(['toggle', 'item-click'])

function resolveItemValue(value, item = null) {
  return typeof value === 'function' ? value({ item, authStore: props.authStore }) : value
}

function hasBadge(item) {
  const value = resolveItemValue(item?.badge, item)
  return value !== undefined && value !== null && value !== ''
}
</script>

<style scoped>
.user-dropdown {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.2s;
}

.user-dropdown:hover {
  background: var(--forum-bg-subtle);
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--forum-primary-color);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.avatar-image {
  object-fit: cover;
}

.username {
  max-width: 88px;
  font-size: 14px;
  color: var(--forum-text-muted);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-dropdown i.fa-caret-down {
  font-size: 12px;
  color: var(--forum-text-soft);
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: 3px;
  box-shadow: var(--forum-shadow-md);
  min-width: 200px;
  z-index: 1000;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 15px;
  border: 0;
  background: transparent;
  color: var(--forum-text-muted);
  font-size: 14px;
  font-family: inherit;
  text-align: left;
  text-decoration: none;
  appearance: none;
  transition: background 0.2s;
  cursor: pointer;
  box-sizing: border-box;
}

.dropdown-item:hover {
  background: var(--forum-bg-subtle);
  text-decoration: none;
}

.dropdown-item--active {
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
}

.dropdown-item i {
  width: 16px;
  font-size: 14px;
  color: var(--forum-text-soft);
}

.dropdown-item--danger,
.dropdown-item--danger i {
  color: #e74c3c;
}

.dropdown-badge {
  margin-left: auto;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(77, 105, 142, 0.12);
  color: var(--forum-primary-color);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.dropdown-divider {
  height: 1px;
  background: var(--forum-border-color);
  margin: 5px 0;
}
</style>
