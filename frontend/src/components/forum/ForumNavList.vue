<template>
  <div :class="rootClass">
    <template v-for="section in sections" :key="section.key || section.title || 'default'">
      <h4 v-if="section.title" :class="sectionTitleClass">{{ section.title }}</h4>
      <ul :class="sectionListClass">
        <li
          v-for="item in section.items"
          :key="item.key || item.path || item.to || item.label"
          :class="itemWrapperClass"
        >
          <component
            :is="item.href ? 'a' : 'router-link'"
            :to="item.href ? undefined : item.to"
            :href="item.href || undefined"
            :class="[itemClass, { active: item.active, 'is-muted': item.muted }]"
            :title="item.description || ''"
            @click="$emit('select', item)"
          >
            <i v-if="item.icon" :class="item.icon"></i>
            <span>{{ item.label }}</span>
            <small v-if="item.description" :class="itemDescriptionClass">{{ item.description }}</small>
            <span v-if="item.badge" :class="itemBadgeClass">{{ item.badge }}</span>
          </component>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup>
defineProps({
  sections: {
    type: Array,
    default: () => []
  },
  rootClass: {
    type: String,
    default: 'forum-nav-list'
  },
  sectionTitleClass: {
    type: String,
    default: 'forum-nav-list__title'
  },
  sectionListClass: {
    type: String,
    default: 'forum-nav-list__section'
  },
  itemWrapperClass: {
    type: String,
    default: 'forum-nav-list__itemWrap'
  },
  itemClass: {
    type: String,
    default: 'forum-nav-list__item'
  },
  itemDescriptionClass: {
    type: String,
    default: 'forum-nav-list__description'
  },
  itemBadgeClass: {
    type: String,
    default: 'forum-nav-list__badge'
  }
})

defineEmits(['select'])
</script>

<style scoped>
.forum-nav-list__section {
  list-style: none;
  padding: 0;
  margin: 0;
}

.forum-nav-list__item {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
}

.forum-nav-list__description {
  display: none;
}

.forum-nav-list__badge {
  margin-left: auto;
  min-width: 18px;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 11px;
  text-align: center;
}
</style>
