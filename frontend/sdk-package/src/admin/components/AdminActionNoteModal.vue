<template>
  <div v-if="show" class="Modal" @click.self="$emit('close')">
    <div class="Modal-content AdminActionNoteModal">
      <div class="Modal-header">
        <h3>{{ title }}</h3>
        <button type="button" class="Modal-close" :disabled="saving" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>
      <div class="Modal-body">
        <div class="Form-group">
          <label for="admin-action-note">{{ noteLabel }}</label>
          <div v-if="templates.length" class="AdminActionNoteModal-templates">
            <span class="AdminActionNoteModal-templatesLabel">{{ templatesLabel }}</span>
            <div class="AdminActionNoteModal-templateList">
              <button
                v-for="template in templates"
                :key="template.value"
                type="button"
                class="AdminActionNoteModal-templateButton"
                :disabled="saving"
                @click="$emit('select-template', template.value)"
              >
                <span class="AdminActionNoteModal-templateName">{{ template.label }}</span>
                <span v-if="template.description" class="AdminActionNoteModal-templateDesc">{{ template.description }}</span>
              </button>
            </div>
            <p v-if="templatesHint" class="AdminActionNoteModal-templatesHint">{{ templatesHint }}</p>
          </div>
          <textarea
            id="admin-action-note"
            name="note"
            class="FormControl"
            rows="4"
            :value="note"
            :placeholder="placeholder"
            :disabled="saving"
            @input="$emit('update:note', $event.target.value)"
          ></textarea>
        </div>
        <p v-if="description" class="AdminActionNoteModal-description">{{ description }}</p>
      </div>
      <div class="Modal-footer">
        <button type="button" class="Button Button--secondary" :disabled="saving" @click="$emit('close')">
          取消
        </button>
        <button
          type="button"
          class="Button"
          :class="confirmTone === 'danger' ? 'Button--danger' : 'Button--primary'"
          :disabled="saving"
          @click="$emit('submit')"
        >
          {{ saving ? savingText : confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  show: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  noteLabel: {
    type: String,
    default: '备注'
  },
  templatesLabel: {
    type: String,
    default: '常用模板'
  },
  templatesHint: {
    type: String,
    default: ''
  },
  templates: {
    type: Array,
    default: () => []
  },
  note: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: ''
  },
  confirmText: {
    type: String,
    default: '确认'
  },
  savingText: {
    type: String,
    default: '提交中...'
  },
  confirmTone: {
    type: String,
    default: 'primary'
  },
  saving: {
    type: Boolean,
    default: false
  }
})

defineEmits(['update:note', 'close', 'submit', 'select-template'])
</script>

<style scoped>
.AdminActionNoteModal {
  width: min(520px, calc(100vw - 32px));
}

.AdminActionNoteModal-description {
  margin: 10px 0 0;
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
  line-height: 1.6;
}

.AdminActionNoteModal-templates {
  margin-bottom: 12px;
}

.AdminActionNoteModal-templatesLabel {
  display: inline-flex;
  margin-bottom: 8px;
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-xs);
  font-weight: 600;
}

.AdminActionNoteModal-templateList {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
}

.AdminActionNoteModal-templateButton {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  background: var(--forum-bg-elevated-strong);
  color: var(--forum-text-color);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--forum-motion-fast, 120ms) ease, transform var(--forum-motion-fast, 120ms) ease;
}

.AdminActionNoteModal-templateButton:hover:not(:disabled) {
  border-color: var(--forum-primary-color);
  transform: translateY(-1px);
}

.AdminActionNoteModal-templateButton:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.AdminActionNoteModal-templateName {
  font-size: var(--forum-font-size-sm);
  font-weight: 600;
}

.AdminActionNoteModal-templateDesc,
.AdminActionNoteModal-templatesHint {
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-xs);
  line-height: 1.5;
}

.AdminActionNoteModal-templatesHint {
  margin: 8px 0 0;
}

@media (max-width: 768px) {
  .AdminActionNoteModal {
    width: 100%;
    max-width: none;
  }

  .Modal-footer {
    flex-direction: column-reverse;
    align-items: stretch;
  }

  .Modal-footer .Button {
    width: 100%;
    justify-content: center;
  }
}
</style>
