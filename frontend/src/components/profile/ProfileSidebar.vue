<template>
  <aside class="user-sidebar">
    <nav class="side-nav">
      <ul>
        <li v-for="item in items" :key="item.key">
          <a
            class="nav-link"
            :class="{ active: activeTab === item.key }"
            @click.prevent="$emit('change-tab', item.key)"
          >
            <i :class="item.icon"></i>
            <span>{{ item.label }}</span>
            <span v-if="typeof resolveItemCount(item) === 'number'" class="badge-count">{{ resolveItemCount(item) }}</span>
          </a>
        </li>
      </ul>
    </nav>
  </aside>
</template>

<script setup>
defineProps({
  activeTab: {
    type: String,
    required: true
  },
  items: {
    type: Array,
    default: () => []
  }
})

defineEmits(['change-tab'])

function resolveItemCount(item) {
  if (typeof item?.count === 'number') return item.count
  if (typeof item?.badge === 'number') return item.badge
  return null
}
</script>

<style scoped>
.user-sidebar {
  position: sticky;
  top: 76px;
  height: fit-content;
}

.side-nav ul {
  list-style: none;
  padding: 0;
  margin: 0;
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  overflow: hidden;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 14px 18px;
  color: #555;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
}

.side-nav ul li:last-child .nav-link {
  border-bottom: none;
}

.nav-link:hover {
  background: #f8fafb;
  text-decoration: none;
  color: #333;
}

.nav-link.active {
  background: #4d698e;
  color: white;
}

.nav-link i {
  width: 18px;
  text-align: center;
  font-size: 15px;
  flex-shrink: 0;
}

.nav-link span:first-of-type {
  flex: 1;
  min-width: 0;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.badge-count {
  background: rgba(0, 0, 0, 0.08);
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  min-width: 24px;
  text-align: center;
  flex-shrink: 0;
}

.nav-link.active .badge-count {
  background: rgba(255, 255, 255, 0.25);
}

@media (max-width: 768px) {
  .user-sidebar {
    position: static;
  }
}
</style>
