<template>
  <nav class="AdminNav">
    <div class="AdminNav-section">
      <h4 class="AdminNav-title">核心</h4>
      <ul class="AdminNav-list">
        <li v-for="item in coreItems" :key="item.path">
          <router-link
            :to="item.path"
            class="AdminNav-item"
            :class="{ active: isActive(item.path) }"
          >
            <i :class="item.icon"></i>
            <span>{{ item.label }}</span>
          </router-link>
        </li>
      </ul>
    </div>

    <div class="AdminNav-section">
      <h4 class="AdminNav-title">功能</h4>
      <ul class="AdminNav-list">
        <li v-for="item in featureItems" :key="item.path">
          <router-link
            :to="item.path"
            class="AdminNav-item"
            :class="{ active: isActive(item.path) }"
          >
            <i :class="item.icon"></i>
            <span>{{ item.label }}</span>
          </router-link>
        </li>
      </ul>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const coreItems = [
  { path: '/admin', icon: 'fas fa-chart-bar', label: '仪表盘' },
  { path: '/admin/basics', icon: 'fas fa-pencil-alt', label: '基础设置' },
  { path: '/admin/permissions', icon: 'fas fa-key', label: '权限管理' },
  { path: '/admin/appearance', icon: 'fas fa-paint-brush', label: '外观设置' },
  { path: '/admin/users', icon: 'fas fa-users', label: '用户管理' },
]

const featureItems = [
  { path: '/admin/flags', icon: 'fas fa-flag', label: '举报管理' },
  { path: '/admin/tags', icon: 'fas fa-tags', label: '标签管理' },
  { path: '/admin/mail', icon: 'fas fa-envelope', label: '邮件设置' },
  { path: '/admin/advanced', icon: 'fas fa-cog', label: '高级设置' },
]

function isActive(path) {
  if (path === '/admin') {
    return route.path === '/admin'
  }
  return route.path.startsWith(path)
}
</script>

<style scoped>
.AdminNav {
  width: 220px;
  flex-shrink: 0;
}

.AdminNav-section {
  margin-bottom: 30px;
}

.AdminNav-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: #999;
  margin: 0 0 10px 0;
  padding: 0 12px;
  letter-spacing: 0.5px;
}

.AdminNav-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.AdminNav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  color: #555;
  text-decoration: none;
  border-radius: 3px;
  font-size: 14px;
  transition: all 0.2s;
}

.AdminNav-item i {
  width: 18px;
  text-align: center;
  font-size: 14px;
}

.AdminNav-item:hover {
  background: #f0f4f8;
  color: #333;
  text-decoration: none;
}

.AdminNav-item.active {
  background: #4d698e;
  color: white;
}

.AdminNav-item.active:hover {
  background: #3d5875;
}
</style>
