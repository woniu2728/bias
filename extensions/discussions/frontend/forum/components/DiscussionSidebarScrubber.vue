<template>
  <div class="sidebar-section sidebar-section--scrubber">
    <div ref="scrubberPanel" class="scrubber-panel">
      <button type="button" class="scrubber-link" @click="$emit('jump-to-post', 1)">
        <i class="fas fa-angle-double-up"></i>
        {{ startLinkText }}
      </button>

      <div
        ref="scrubberTrack"
        class="scrubber-scrollbar"
        :style="scrubberScrollbarStyle"
        @click="$emit('scrubber-track-click', $event)"
      >
        <div class="scrubber-before" :style="{ height: `${scrubberBeforePercent}%` }"></div>
        <div
          v-if="unreadCount"
          class="scrubber-unread"
          :style="{
            top: `${unreadTopPercent}%`,
            height: `${unreadHeightPercent}%`
          }"
        ></div>
        <div
          class="scrubber-handle"
          :style="{
            top: `${scrubberBeforePercent}%`,
            height: `${scrubberHandlePercent}%`
          }"
          :class="{ 'is-dragging': scrubberDragging }"
          @mousedown="$emit('scrubber-handle-pointerdown', $event)"
          @touchstart="$emit('scrubber-handle-pointerdown', $event)"
          @click.stop
        >
          <div class="scrubber-bar"></div>
          <div class="scrubber-info">
            <strong>{{ scrubberPositionText }}</strong>
            <span class="scrubber-description">{{ scrubberDescription }}</span>
          </div>
        </div>
        <div class="scrubber-after" :style="{ height: `${scrubberAfterPercent}%` }"></div>
      </div>

      <button type="button" class="scrubber-link" @click="$emit('jump-to-post', maxPostNumber)">
        <i class="fas fa-angle-double-down"></i>
        {{ endLinkText }}
      </button>
    </div>
  </div>
</template>

<script setup>

import {
  ref,
  computed } from '@bias/core'
import { getUiCopy
} from '@bias/forum'

defineProps({
  scrubberScrollbarStyle: {
    type: Object,
    default: () => ({})
  },
  scrubberBeforePercent: {
    type: Number,
    default: 0
  },
  scrubberAfterPercent: {
    type: Number,
    default: 0
  },
  scrubberHandlePercent: {
    type: Number,
    default: 100
  },
  scrubberDragging: {
    type: Boolean,
    default: false
  },
  unreadCount: {
    type: Number,
    default: 0
  },
  unreadTopPercent: {
    type: Number,
    default: 0
  },
  unreadHeightPercent: {
    type: Number,
    default: 0
  },
  scrubberPositionText: {
    type: String,
    default: ''
  },
  scrubberDescription: {
    type: String,
    default: ''
  },
  maxPostNumber: {
    type: Number,
    default: 1
  }
})

defineEmits([
  'jump-to-post',
  'scrubber-track-click',
  'scrubber-handle-pointerdown'
])

const scrubberPanel = ref(null)
const scrubberTrack = ref(null)

function getScrubberPanelEl() {
  return scrubberPanel.value
}

function getScrubberTrackEl() {
  return scrubberTrack.value
}

defineExpose({
  getScrubberPanelEl,
  getScrubberTrackEl
})

const startLinkText = computed(() => getUiCopy({
  surface: 'discussion-sidebar-scrubber-start',
})?.text || '原帖')

const endLinkText = computed(() => getUiCopy({
  surface: 'discussion-sidebar-scrubber-end',
})?.text || '现在')
</script>

<style scoped>
.sidebar-section {
  background: var(--forum-bg-elevated);
  padding: 20px;
  border-radius: var(--forum-radius-md);
  margin-bottom: 20px;
  box-shadow: var(--forum-shadow-sm);
}

.sidebar-section--scrubber {
  padding: 18px 18px 14px;
}

.scrubber-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scrubber-link {
  border: 0;
  background: transparent;
  color: var(--forum-text-muted);
  padding: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  width: fit-content;
  cursor: pointer;
}

.scrubber-link:hover {
  color: var(--forum-text-color);
}

.scrubber-scrollbar {
  margin: 8px 0 8px 3px;
  height: 300px;
  min-height: 50px;
  position: relative;
  cursor: pointer;
  user-select: none;
}

.scrubber-before,
.scrubber-after {
  position: absolute;
  left: 0;
  width: 100%;
  border-left: 1px solid var(--forum-border-color);
}

.scrubber-before {
  top: 0;
}

.scrubber-after {
  bottom: 0;
}

.scrubber-unread {
  position: absolute;
  left: 0;
  width: 100%;
  border-left: 1px solid var(--forum-border-strong);
  background-image: linear-gradient(to right, rgba(230, 235, 241, 0.92), transparent 10px, transparent);
  display: flex;
  align-items: center;
  color: var(--forum-text-soft);
  text-transform: uppercase;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  padding-left: 13px;
  pointer-events: none;
}

.scrubber-handle {
  position: absolute;
  left: 0;
  width: 100%;
  padding: 5px 0;
  cursor: move;
  z-index: 1;
}

.scrubber-bar {
  height: 100%;
  width: 5px;
  background: var(--forum-primary-color);
  border-radius: 4px;
  margin-left: -2px;
  transition: background 0.2s;
}

.scrubber-info {
  position: absolute;
  top: 50%;
  left: 15px;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  width: max-content;
  max-width: calc(100% - 15px);
  pointer-events: none;
}

.scrubber-info strong {
  color: var(--forum-text-color);
  font-size: var(--forum-font-size-sm);
  line-height: 1;
  white-space: nowrap;
}

.scrubber-description {
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-xs);
  line-height: 1;
  white-space: nowrap;
}

.scrubber-handle.is-dragging .scrubber-bar,
:global(body.scrubber-dragging) .scrubber-bar {
  background: var(--forum-accent-color);
}

:global(body.scrubber-dragging) {
  cursor: move;
}
</style>
