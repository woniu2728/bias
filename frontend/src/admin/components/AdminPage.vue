<template>
  <div class="AdminPage" :class="className">
    <div class="AdminPage-header">
      <div class="AdminPage-container">
        <h2 class="AdminPage-title">
          <i :class="icon"></i>
          <span>{{ title }}</span>
        </h2>
        <p class="AdminPage-description">{{ description }}</p>
      </div>
    </div>

    <div class="AdminPage-content">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
defineProps({
  className: {
    type: String,
    default: ''
  },
  icon: {
    type: String,
    required: true
  },
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.AdminPage {
  background: transparent;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  padding-bottom: 24px;
}

.AdminPage-header {
  margin-bottom: 20px;
  padding: 20px 0;
  background: var(--forum-bg-subtle);
}

.AdminPage-container {
  width: 100%;
  padding: 0 30px;
  margin: 0;
}

.AdminPage-title {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 0 0 10px;
  color: var(--forum-text-muted);
  font-size: 30px;
  font-weight: 600;
  line-height: 1.15;
}

.AdminPage-title i {
  color: #4d698e;
  font-size: 20px;
}

.AdminPage-description {
  max-width: 880px;
  font-size: 15px;
  color: #60758b;
  margin: 0;
  line-height: 1.5;
}

.AdminPage-content {
  padding: 0;
}

@media (max-width: 768px) {
  .AdminPage-header {
    margin-bottom: 16px;
    padding: 16px 0;
  }

  .AdminPage-title {
    font-size: 26px;
    gap: 12px;
  }

  .AdminPage-title i {
    font-size: 18px;
  }

  .AdminPage-description {
    font-size: 14px;
  }
}

@media (max-width: 480px) {
  .AdminPage-container {
    padding: 0 16px;
  }
}
</style>
