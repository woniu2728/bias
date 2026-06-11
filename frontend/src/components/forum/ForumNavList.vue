<template>
  <div :class="['forum-nav-list', rootClass]">
    <template v-for="section in sections" :key="section.key || section.title || 'default'">
      <h4 v-if="section.title" :class="['forum-nav-list__title', sectionTitleClass]">{{ section.title }}</h4>
      <ul :class="['forum-nav-list__section', sectionListClass]">
        <li
          v-for="item in section.items"
          :key="item.key || item.path || item.to || item.label"
          :class="['forum-nav-list__itemWrap', itemWrapperClass]"
        >
          <component
            :is="item.href ? 'a' : 'router-link'"
            :to="item.href ? undefined : item.to"
            :href="item.href || undefined"
            :style="item.style || undefined"
            :class="['forum-nav-list__item', itemClass, { active: item.active, 'is-muted': item.muted }]"
            @click="$emit('select', item)"
          >
            <i v-if="item.icon" :class="item.icon"></i>
            <span class="forum-nav-list__content">
              <span class="forum-nav-list__label">{{ item.label }}</span>
              <small
                v-if="showDescriptions && item.description"
                :class="['forum-nav-list__description', itemDescriptionClass]"
              >{{ item.description }}</small>
            </span>
            <span v-if="item.badge" :class="['forum-nav-list__badge', itemBadgeClass]">{{ item.badge }}</span>
            <span
              v-if="showTooltips && item.description"
              :class="['forum-nav-list__tooltip', tooltipClass]"
              role="tooltip"
            >{{ item.description }}</span>
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
  },
  tooltipClass: {
    type: String,
    default: 'forum-nav-list__tooltip'
  },
  showDescriptions: {
    type: Boolean,
    default: true
  },
  showTooltips: {
    type: Boolean,
    default: false
  }
})

defineEmits(['select'])
</script>

<style scoped>
.forum-nav-list {
  min-width: 0;
}

.forum-nav-list__title {
  margin: 0;
}

.forum-nav-list__section {
  list-style: none;
  padding: 0;
  margin: 0;
}

.forum-nav-list__itemWrap {
  list-style: none;
  margin: 0;
}

.forum-nav-list__item {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
  text-decoration: none;
}

.forum-nav-list__content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.forum-nav-list__label {
  min-width: 0;
}

.forum-nav-list__item i {
  width: 18px;
  text-align: center;
  flex-shrink: 0;
}

.forum-nav-list__description {
  display: block;
}

.forum-nav-list__badge {
  margin-left: auto;
  min-width: 18px;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 11px;
  text-align: center;
}

.forum-nav-list__tooltip {
  position: absolute;
  top: 50%;
  left: calc(100% + 12px);
  z-index: 30;
  width: max-content;
  max-width: min(280px, calc(100vw - 120px));
  padding: 10px 12px;
  border: 1px solid rgba(114, 132, 153, 0.2);
  border-radius: 12px;
  background: rgba(24, 36, 51, 0.96);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.2);
  color: #f4f7fb;
  font-size: 13px;
  line-height: 1.5;
  white-space: normal;
  opacity: 0;
  pointer-events: none;
  transform: translate3d(-6px, -50%, 0);
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.forum-nav-list__tooltip::before {
  content: '';
  position: absolute;
  top: 50%;
  left: -6px;
  width: 12px;
  height: 12px;
  background: inherit;
  border-left: 1px solid rgba(114, 132, 153, 0.2);
  border-bottom: 1px solid rgba(114, 132, 153, 0.2);
  transform: translateY(-50%) rotate(45deg);
}

.forum-nav-list__item:hover .forum-nav-list__tooltip,
.forum-nav-list__item:focus-visible .forum-nav-list__tooltip {
  opacity: 1;
  transform: translate3d(0, -50%, 0);
}
</style>
