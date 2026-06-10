<template>
  <router-link :to="to" class="nav-item" :class="{ active }">
    <i :class="icon"></i>
    <span>{{ label }}</span>
  </router-link>
</template>

<script setup>
defineProps({
  active: {
    type: Boolean,
    default: false
  },
  icon: {
    type: String,
    required: true
  },
  label: {
    type: String,
    required: true
  },
  to: {
    type: [String, Object],
    required: true
  }
})
</script>

<style scoped>
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0;
  color: #75808c;
  text-decoration: none;
  transition: color 0.15s ease;
  font-size: 13px;
  font-weight: normal;
  cursor: pointer;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  border-radius: 3px;
  margin-bottom: 0;
  line-height: 20px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  user-select: none;
  box-shadow: none;
  min-height: 18px;
}

.nav-item:hover {
  background: none;
  color: var(--forum-primary-color);
  text-decoration: none;
}

.nav-item.active {
  background: none;
  color: inherit;
  font-weight: 700;
}

.nav-item i {
  width: 16px;
  text-align: center;
  font-size: 14px;
}
</style>
