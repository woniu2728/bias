<template>
  <article
    class="result-card"
    :class="{ 'user-card': userLayout }"
    @click="$emit('click')"
  >
    <div class="result-card-icon" :class="{ 'result-card-icon--avatar': avatarMode }">
      <img
        v-if="avatarUrl"
        :src="avatarUrl"
        :alt="avatarAlt"
        class="result-avatar"
      />
      <span v-else-if="avatarText">{{ avatarText }}</span>
      <i v-else :class="iconClass"></i>
    </div>
    <div class="result-card-main">
      <h3 v-html="titleHtml"></h3>
      <p v-html="excerptHtml"></p>
      <div class="result-meta">
        <span v-for="item in metaItems" :key="item">{{ item }}</span>
      </div>
    </div>
  </article>
</template>

<script setup>
defineProps({
  avatarAlt: {
    type: String,
    default: ''
  },
  avatarMode: {
    type: Boolean,
    default: false
  },
  avatarText: {
    type: String,
    default: ''
  },
  avatarUrl: {
    type: String,
    default: ''
  },
  excerptHtml: {
    type: String,
    required: true
  },
  iconClass: {
    type: String,
    default: 'far fa-comments'
  },
  metaItems: {
    type: Array,
    default: () => []
  },
  titleHtml: {
    type: String,
    required: true
  },
  userLayout: {
    type: Boolean,
    default: false
  }
})

defineEmits(['click'])
</script>

<style scoped>
.result-card {
  display: flex;
  gap: 14px;
  padding: 18px 20px;
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
  box-shadow: var(--forum-shadow-sm);
}

.result-card:hover {
  border-color: color-mix(in srgb, var(--forum-primary-color) 28%, white);
  box-shadow: var(--forum-shadow-md);
  transform: translateY(-1px);
}

.result-card-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--forum-primary-color) 12%, white);
  color: var(--forum-primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.result-card-icon--avatar {
  background: #eef3f7;
  color: #506274;
}

.result-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.result-card-main {
  min-width: 0;
}

.result-card-main h3 {
  font-size: 17px;
  color: var(--forum-text-color);
  margin-bottom: 6px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.result-card-main p {
  color: var(--forum-text-muted);
  line-height: 1.7;
  margin-bottom: 8px;
  overflow-wrap: anywhere;
}

.result-card-main :deep(mark) {
  background: rgba(255, 220, 126, 0.55);
  color: inherit;
  padding: 0 2px;
  border-radius: 4px;
}

.result-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--forum-text-soft);
  font-size: 12px;
}

.user-card {
  align-items: center;
}

@media (max-width: 520px) {
  .result-card {
    gap: 12px;
    padding: 15px;
  }

  .result-card-icon {
    width: 36px;
    height: 36px;
  }

  .result-card-main h3 {
    font-size: 16px;
  }
}
</style>
