<template>
  <section class="ProfilePointsSection">
    <header class="ProfilePointsSection-header">
      <div>
        <h2>{{ titleText }}</h2>
        <p>{{ descriptionText }}</p>
      </div>
      <div class="ProfilePointsSection-balance">
        <span class="ProfilePointsSection-value">{{ balance }}</span>
        <span class="ProfilePointsSection-unit">{{ unitText }}</span>
      </div>
    </header>

    <div class="ProfilePointsSection-grid">
      <div
        v-for="item in stats"
        :key="item.key"
        class="ProfilePointsSection-stat"
      >
        <i :class="item.icon"></i>
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </div>
  </section>
</template>

<script setup>
import {
  computed,
} from '@bias/core'
import {
  getUiCopy,
} from '@bias/forum'
import {
  getUserPointsBalance,
} from './pointsRuntime.js'

const props = defineProps({
  user: {
    type: Object,
    required: true
  }
})

const balance = computed(() => getUserPointsBalance(props.user))
const titleText = computed(() => getUiCopy({
  surface: 'points-profile-title',
})?.text || '积分')
const descriptionText = computed(() => getUiCopy({
  surface: 'points-profile-description',
})?.text || '积分可通过发起讨论、发表回复和收到点赞获得，也可用于消耗型扩展能力。')
const unitText = computed(() => getUiCopy({
  surface: 'points-profile-unit',
})?.text || '分')
const stats = computed(() => [
  {
    key: 'discussion-reward',
    icon: 'fas fa-pen-to-square',
    label: getUiCopy({ surface: 'points-profile-discussion-reward-label' })?.text || '发主题奖励',
    value: '+10',
  },
  {
    key: 'reply-reward',
    icon: 'far fa-comment',
    label: getUiCopy({ surface: 'points-profile-reply-reward-label' })?.text || '回复奖励',
    value: '+3',
  },
  {
    key: 'ai-cost',
    icon: 'fas fa-wand-magic-sparkles',
    label: getUiCopy({ surface: 'points-profile-ai-cost-label' })?.text || 'AI 能力消耗',
    value: '-2 起',
  },
])
</script>

<style scoped>
.ProfilePointsSection {
  padding: 24px;
}

.ProfilePointsSection-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 22px;
  border-bottom: 1px solid #e8edf2;
}

.ProfilePointsSection h2 {
  margin: 0 0 8px;
  color: #233445;
  font-size: 20px;
}

.ProfilePointsSection p {
  max-width: 560px;
  margin: 0;
  color: #667788;
  font-size: 14px;
  line-height: 1.7;
}

.ProfilePointsSection-balance {
  min-width: 132px;
  padding: 16px 18px;
  border: 1px solid #dbe5ee;
  border-radius: 8px;
  background: #f8fbfd;
  text-align: right;
}

.ProfilePointsSection-value {
  display: block;
  color: #25384d;
  font-size: 34px;
  font-weight: 700;
  line-height: 1;
}

.ProfilePointsSection-unit {
  display: block;
  margin-top: 6px;
  color: #718294;
  font-size: 13px;
}

.ProfilePointsSection-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.ProfilePointsSection-stat {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 10px;
  align-items: center;
  padding: 14px;
  border: 1px solid #e5ebf1;
  border-radius: 8px;
  background: #ffffff;
  color: #526579;
  font-size: 13px;
}

.ProfilePointsSection-stat i {
  color: #b8872b;
}

.ProfilePointsSection-stat strong {
  grid-column: 1 / -1;
  color: #233445;
  font-size: 18px;
}

@media (max-width: 768px) {
  .ProfilePointsSection {
    padding: 18px;
  }

  .ProfilePointsSection-header {
    flex-direction: column;
  }

  .ProfilePointsSection-balance {
    width: 100%;
    text-align: left;
  }

  .ProfilePointsSection-grid {
    grid-template-columns: 1fr;
  }
}
</style>
