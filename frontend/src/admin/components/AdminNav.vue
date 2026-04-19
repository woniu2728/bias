<template>
  <nav class="AdminNav" :class="{ 'is-mobile-open': mobileOpen }">
    <div v-if="mobileOpen" class="AdminNav-backdrop" @click="$emit('close')"></div>
    <div class="AdminNav-panel">
      <div class="AdminNav-mobileHeader">
        <strong>后台导航</strong>
        <button type="button" class="AdminNav-close" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="AdminNav-section">
        <h4 class="AdminNav-title">核心</h4>
        <ul class="AdminNav-list">
          <li v-for="item in coreItems" :key="item.path">
            <router-link
              :to="item.path"
              class="AdminNav-item"
              :class="{ active: isActive(item.path) }"
              @click="$emit('close')"
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
              @click="$emit('close')"
            >
              <i :class="item.icon"></i>
              <span>{{ item.label }}</span>
            </router-link>
          </li>
        </ul>
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
import { useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { coreItems, featureItems, isAdminPathActive } from '../navigation'

defineProps({
  mobileOpen: {
    type: Boolean,
    default: false
  }
})

defineEmits(['close'])

const route = useRoute()
const authStore = useAuthStore()

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
  width: 220px;
  flex-shrink: 0;
}

.AdminNav-mobileHeader,
.AdminNav-backdrop {
  display: none;
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

.AdminNav-item--danger {
  border: 0;
  width: 100%;
  background: #fff4f3;
  color: #b34c45;
  cursor: pointer;
}

@media (max-width: 960px) {
  .AdminNav {
    width: 100%;
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
    padding: 14px 14px 20px;
    background: #fff;
    box-shadow: 0 18px 40px rgba(31, 45, 61, 0.18);
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
    border-bottom: 1px solid #e7edf3;
    color: #31465d;
    font-size: 15px;
  }

  .AdminNav-close {
    width: 36px;
    height: 36px;
    padding: 0;
    border: 0;
    border-radius: 999px;
    background: #f4f7fa;
    color: #607285;
  }

  .AdminNav-section {
    margin-bottom: 18px;
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
    border-top: 1px solid #e7edf3;
  }
}
</style>
