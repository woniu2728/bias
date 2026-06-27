<template>
  <section class="ExtensionGeneratedPermissions">
    <section v-if="permissionSections.length" class="ExtensionGeneratedPermissions-panel">
      <div
        v-for="section in permissionSections"
        :key="section.name"
        class="ExtensionGeneratedPermissions-section"
      >
        <header class="ExtensionGeneratedPermissions-sectionHeader">
          <div>
            <h4>{{ section.label }}</h4>
          </div>
        </header>

        <div class="ExtensionGeneratedPermissions-list">
          <article
            v-for="permission in section.permissions"
            :key="permission.name"
            class="ExtensionGeneratedPermissions-item"
          >
            <div class="ExtensionGeneratedPermissions-itemMain">
              <div class="ExtensionGeneratedPermissions-itemTitle">
                <i v-if="permission.icon" :class="permission.icon"></i>
                <strong>{{ permission.label }}</strong>
              </div>
              <code>{{ permission.name }}</code>
            </div>
            <p v-if="permission.description" class="ExtensionGeneratedPermissions-itemDescription">
              {{ permission.description }}
            </p>
            <div class="ExtensionGeneratedPermissions-itemMeta">
              <span>模块：{{ permission.module_id }}</span>
              <span v-if="permission.required_permissions?.length">
                依赖：{{ permission.required_permissions.join('、') }}
              </span>
            </div>
          </article>
        </div>
      </div>
    </section>

    <AdminStateBlock v-else tone="subtle">
      当前扩展暂未注册独立权限项，或相关模块尚未启用。
    </AdminStateBlock>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
const props = defineProps({
  extension: {
    type: Object,
    default: null,
  },
})

const permissionSummary = computed(() => (
  props.extension?.permission_summary || { permission_count: 0, section_count: 0, module_count: 0 }
))
const permissionSections = computed(() => (
  Array.isArray(props.extension?.permission_sections) ? props.extension.permission_sections : []
))
</script>

<style scoped>
.ExtensionGeneratedPermissions {
  display: flex;
  flex-direction: column;
}

.ExtensionGeneratedPermissions-panel {
  padding: 0;
}

.ExtensionGeneratedPermissions-section + .ExtensionGeneratedPermissions-section {
  margin-top: 22px;
  padding-top: 22px;
  border-top: 1px solid #e5ebf3;
}

.ExtensionGeneratedPermissions-sectionHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.ExtensionGeneratedPermissions-sectionHeader h4 {
  margin: 0;
  color: #5f7798;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.ExtensionGeneratedPermissions-itemDescription {
  margin: 0;
}

.ExtensionGeneratedPermissions-list {
  display: grid;
  gap: 0;
}

.ExtensionGeneratedPermissions-item {
  display: grid;
  gap: 8px;
  padding: 14px 0;
  border-bottom: 1px solid #edf2f7;
  border-radius: 0;
  background: transparent;
}

.ExtensionGeneratedPermissions-item:last-child {
  border-bottom: 0;
}

.ExtensionGeneratedPermissions-itemMain {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
}

.ExtensionGeneratedPermissions-itemTitle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.ExtensionGeneratedPermissions-itemTitle i {
  color: #6d83a4;
}

.ExtensionGeneratedPermissions-itemMeta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  font-size: 13px;
  color: var(--forum-text-soft);
}
</style>
