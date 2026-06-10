<template>
  <div class="discussion-list-item-author">
    <router-link :to="buildUserPath(discussion.user)" class="avatar-link">
      <img
        v-if="discussion.user?.avatar_url"
        :src="discussion.user.avatar_url"
        :alt="getUserDisplayName(discussion.user)"
        class="avatar avatar-image"
      />
      <div v-else class="avatar" :style="{ backgroundColor: getUserAvatarColor(discussion.user) }">
        {{ getUserInitial(discussion.user) }}
      </div>
    </router-link>

    <div v-if="discussionBadges.length" class="discussion-list-item-badges">
      <span
        v-for="badge in discussionBadges"
        :key="badge.key"
        class="badge"
        :class="badge.className"
        :title="badge.title || ''"
      >
        <i v-if="badge.icon" :class="badge.icon"></i>
      </span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  discussion: {
    type: Object,
    required: true
  },
  discussionBadges: {
    type: Array,
    default: () => []
  },
  buildUserPath: {
    type: Function,
    required: true
  },
  getUserAvatarColor: {
    type: Function,
    required: true
  },
  getUserDisplayName: {
    type: Function,
    required: true
  },
  getUserInitial: {
    type: Function,
    required: true
  }
})
</script>

<style scoped>
.discussion-list-item-author {
  position: relative;
  flex-shrink: 0;
}

.avatar-link {
  display: block;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  font-weight: 600;
}

.avatar-image {
  object-fit: cover;
}

.discussion-list-item-badges {
  position: absolute;
  top: -14px;
  left: -2px;
  display: flex;
  gap: 4px;
}

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 3px;
  font-size: 10px;
}

.badge-pinned {
  background: #ffc107;
  color: #856404;
}

.badge-locked {
  background: #999;
  color: white;
}

@media (max-width: 768px) {
  .avatar {
    width: 32px;
    height: 32px;
    font-size: 13px;
  }

  .discussion-list-item-badges {
    top: -12px;
    left: -4px;
  }

  .badge {
    width: 18px;
    height: 18px;
    font-size: 9px;
  }
}
</style>
