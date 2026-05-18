<template>
  <footer class="footer">
    <div class="container">
      <div
        v-if="footerHtml"
        class="footer-html"
        v-html="footerHtml"
      ></div>
      <p v-else>Powered by <strong>{{ forumStore.settings.forum_title }}</strong> - Django + Vue 3</p>
    </div>
  </footer>
</template>

<script setup>
import { computed } from 'vue'
import { useForumStore } from '@/stores/forum'

const forumStore = useForumStore()
const footerHtml = computed(() => String(forumStore.settings.custom_footer_html || '').trim())
</script>

<style scoped>
.footer {
  background: white;
  border-top: 1px solid #e3e8ed;
  color: #999;
  padding: 20px 0;
  text-align: center;
  margin-top: 40px;
  font-size: 12px;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.footer p {
  margin: 0;
}

.footer-html {
  color: inherit;
}

.footer-html :deep(*) {
  max-width: 100%;
}

.footer strong {
  color: var(--forum-primary-color);
  font-weight: 600;
}
</style>
