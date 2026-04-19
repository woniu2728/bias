<template>
  <div class="AdminPage" :class="className">
    <div class="AdminPage-header">
      <div class="AdminPage-headerIcon">
        <i :class="icon"></i>
      </div>
      <div class="AdminPage-headerContent">
        <h2 class="AdminPage-title">{{ title }}</h2>
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
  background: white;
  border-radius: 3px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.AdminPage-header {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  padding: 30px;
  border-bottom: 1px solid #e3e8ed;
}

.AdminPage-headerIcon {
  width: 50px;
  height: 50px;
  background: #f5f8fa;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.AdminPage-headerIcon i {
  font-size: 20px;
  color: #4d698e;
}

.AdminPage-headerContent {
  flex: 1;
}

.AdminPage-title {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px 0;
}

.AdminPage-description {
  font-size: 14px;
  color: #666;
  margin: 0;
  line-height: 1.6;
}

.AdminPage-content {
  padding: 30px;
}

@media (max-width: 768px) {
  .AdminPage {
    border-radius: 0;
    box-shadow: none;
  }

  .AdminPage-header {
    gap: 14px;
    padding: 18px 16px;
    background: #f4f6f8;
  }

  .AdminPage-headerIcon {
    width: 42px;
    height: 42px;
  }

  .AdminPage-headerIcon i {
    font-size: 18px;
  }

  .AdminPage-title {
    font-size: 20px;
  }

  .AdminPage-description {
    font-size: 13px;
  }

  .AdminPage-content {
    padding: 18px 16px;
  }
}

@media (max-width: 480px) {
  .AdminPage-header {
    align-items: flex-start;
    padding: 16px 14px;
  }

  .AdminPage-title {
    font-size: 18px;
  }

  .AdminPage-content {
    padding: 16px 14px;
  }
}
</style>
