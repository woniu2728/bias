<template>
  <div class="profile-section settings-section">
    <div class="profile-section-header">
      <div>
        <h2>{{ sectionTitleText }}</h2>
        <p>{{ sectionDescriptionText }}</p>
      </div>
    </div>

    <ForumInlineMessage v-if="settingsSuccess" tone="success">{{ settingsSuccess }}</ForumInlineMessage>
    <ForumInlineMessage v-if="settingsError" tone="danger">{{ settingsError }}</ForumInlineMessage>

    <div class="profile-settings-card">
      <div class="profile-form-group">
        <label for="profile-display-name">{{ displayNameLabelText }}</label>
        <input
          id="profile-display-name"
          class="profile-form-control"
          :value="editForm.display_name"
          name="display_name"
          :placeholder="displayNamePlaceholderText"
          type="text"
          @input="$emit('update-edit-form', { key: 'display_name', value: $event.target.value })"
        />
      </div>

      <div class="profile-form-group">
        <label for="profile-email">{{ emailLabelText }}</label>
        <input
          id="profile-email"
          class="profile-form-control"
          :value="editForm.email"
          name="email"
          :placeholder="emailPlaceholderText"
          type="email"
          @input="$emit('update-edit-form', { key: 'email', value: $event.target.value })"
        />
        <small class="profile-form-help">
          {{ emailHelpText }}
        </small>
      </div>

      <div class="profile-form-group">
        <label for="profile-bio">{{ bioLabelText }}</label>
        <textarea
          id="profile-bio"
          class="profile-form-control"
          :value="editForm.bio"
          name="bio"
          :placeholder="bioPlaceholderText"
          rows="5"
          @input="$emit('update-edit-form', { key: 'bio', value: $event.target.value })"
        ></textarea>
      </div>

      <div class="profile-form-actions">
        <button type="button" class="primary" :disabled="saving" @click="$emit('save-profile')">
          {{ saveProfileButtonText }}
        </button>
      </div>
    </div>

    <div class="profile-settings-card profile-settings-card--stacked">
      <div class="profile-card-header">
        <div>
          <h3>{{ preferencesTitleText }}</h3>
          <p>{{ preferencesDescriptionText }}</p>
        </div>
        <button
          type="button"
          class="secondary"
          :disabled="loadingPreferences || savingPreferences"
          @click="$emit('save-preferences')"
        >
          {{ savePreferencesButtonText }}
        </button>
      </div>

      <ForumInlineMessage v-if="preferencesSuccess" tone="success">{{ preferencesSuccess }}</ForumInlineMessage>
      <ForumInlineMessage v-if="preferencesError" tone="danger">{{ preferencesError }}</ForumInlineMessage>
      <ForumStateBlock v-if="loadingPreferences" class="section-state-block section-state-block--compact">{{ preferencesLoadingStateText }}</ForumStateBlock>
      <div v-else class="preferences-groups">
        <section
          v-for="group in groupedPreferences"
          :key="group.key"
          class="preferences-group"
        >
          <header class="preferences-group-header">
            <h4>{{ group.label }}</h4>
            <p>{{ group.description }}</p>
          </header>

          <div class="preferences-list">
            <label
              v-for="item in group.items"
              :key="item.key"
              class="preference-item"
            >
              <span class="preference-copy">
                <strong>{{ item.label }}</strong>
                <small>{{ item.description }}</small>
              </span>
              <input
                :checked="Boolean(preferences.values?.[item.key])"
                :name="item.key"
                type="checkbox"
                @change="$emit('update-preference', {
                  key: item.key,
                  value: $event.target.checked
                })"
              />
            </label>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  toRef } from '@bias/core'
import { ForumInlineMessage,
  ForumStateBlock
} from '@bias/forum'
import { useProfileSettingsSectionState } from './useProfileSettingsSectionState'

const props = defineProps({
  user: {
    type: Object,
    required: true
  },
  editForm: {
    type: Object,
    required: true
  },
  preferences: {
    type: Object,
    required: true
  },
  saving: {
    type: Boolean,
    default: false
  },
  settingsSuccess: {
    type: String,
    default: ''
  },
  settingsError: {
    type: String,
    default: ''
  },
  loadingPreferences: {
    type: Boolean,
    default: false
  },
  savingPreferences: {
    type: Boolean,
    default: false
  },
  preferencesSuccess: {
    type: String,
    default: ''
  },
  preferencesError: {
    type: String,
    default: ''
  }
})

const {
  bioLabelText,
  bioPlaceholderText,
  displayNameLabelText,
  displayNamePlaceholderText,
  emailHelpText,
  emailLabelText,
  emailPlaceholderText,
  groupedPreferences,
  preferencesDescriptionText,
  preferencesLoadingStateText,
  preferencesTitleText,
  savePreferencesButtonText,
  saveProfileButtonText,
  sectionDescriptionText,
  sectionTitleText,
} = useProfileSettingsSectionState({
  loadingPreferences: toRef(props, 'loadingPreferences'),
  preferences: toRef(props, 'preferences'),
  saving: toRef(props, 'saving'),
  savingPreferences: toRef(props, 'savingPreferences'),
  user: toRef(props, 'user'),
})

defineEmits(['save-profile', 'save-preferences', 'update-edit-form', 'update-preference'])
</script>

<style scoped>
.section-state-block {
  margin: 0;
}

.section-state-block--compact {
  padding: 18px 16px;
}

.preferences-groups {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.preferences-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preferences-group-header h4 {
  margin: 0;
  font-size: 15px;
  color: #203040;
}

.preferences-group-header p {
  margin: 4px 0 0;
  font-size: 13px;
  color: #728090;
}

.preferences-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preference-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: white;
  border: 1px solid #e7edf2;
}

.preference-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #324150;
  min-width: 0;
}

.preference-copy small {
  color: #7d8b97;
  overflow-wrap: anywhere;
}

.preference-item input {
  width: 18px;
  height: 18px;
  accent-color: #4d698e;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .preference-item {
    flex-direction: column;
    align-items: flex-start;
  }

  .preference-item {
    gap: 12px;
  }
}
</style>
