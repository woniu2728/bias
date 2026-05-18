<template>
  <AdminPage
    class-name="AdvancedPage"
    icon="fas fa-cog"
    :title="advancedCopy?.pageTitle || '高级设置'"
    :description="advancedCopy?.pageDescription || '配置缓存、队列、维护模式与文件存储'"
  >
    <div class="AdvancedPage-content">
      <div class="RuntimeNotice">
        <h3 class="Section-title">{{ advancedCopy?.runtimeNoticeTitle || '运行时说明' }}</h3>
        <div class="RuntimeNotice-grid">
          <div>
            <h4>{{ advancedCopy?.immediateEffectTitle || '即时生效' }}</h4>
            <p>{{ advancedCopy?.immediateEffectDescription || '`maintenance_mode`、`maintenance_message`、`cache_lifetime`、`log_queries` 会在保存后直接影响请求层行为。' }}</p>
          </div>
          <div>
            <h4>{{ advancedCopy?.deploymentRequiredTitle || '需额外部署或重启' }}</h4>
            <p>{{ advancedCopy?.deploymentRequiredDescription || '`debug_mode` 由 Django 配置文件或环境变量控制；`queue_enabled` / `queue_driver` 会控制已接入队列入口的任务，新 worker 配置需重启服务后生效。' }}</p>
          </div>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.cacheSectionTitle || '缓存设置' }}</h3>

        <div class="Form-group">
          <label for="advanced-cache-driver">{{ advancedCopy?.cacheDriverLabel || '缓存驱动' }}</label>
          <select
            id="advanced-cache-driver"
            v-model="settings.cache_driver"
            name="cache_driver"
            class="FormControl"
          >
            <option v-for="option in cacheDriverOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <p class="Form-help">{{ advancedCopy?.cacheDriverHelpText || '选择缓存存储方式' }}</p>
        </div>

        <div class="Form-group">
          <label for="advanced-cache-lifetime">{{ advancedCopy?.cacheLifetimeLabel || '缓存时间（秒）' }}</label>
          <input
            id="advanced-cache-lifetime"
            v-model.number="settings.cache_lifetime"
            name="cache_lifetime"
            type="number"
            class="FormControl"
            :placeholder="advancedConfig?.placeholders?.cacheLifetime || '3600'"
          />
          <p class="Form-help">{{ advancedCopy?.cacheLifetimeHelpText || '当前已接入公开论坛设置缓存。填 0 表示禁用该缓存，保存基础/外观/高级设置时会自动清理。' }}</p>
        </div>

        <div class="Form-actions">
          <button type="button" class="Button" :disabled="clearing" @click="clearCache">
            {{ clearing ? (advancedCopy?.clearingCacheLabel || '清除中...') : (advancedCopy?.clearCacheLabel || '清除缓存') }}
          </button>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.searchSectionTitle || '搜索索引' }}</h3>

        <div class="RuntimeSnapshot">
          <div class="RuntimeSnapshot-grid">
            <div class="RuntimeSnapshot-item">
              <div class="RuntimeSnapshot-label">{{ advancedCopy?.searchStatusLabel || '当前状态' }}</div>
              <div class="RuntimeSnapshot-value">
                {{ searchIndexStatus?.label || advancedCopy?.searchStatusLoadingText || '加载中...' }}
              </div>
              <p class="RuntimeSnapshot-help">
                {{ searchIndexStatus?.message || searchIndexStatusError || advancedCopy?.searchStatusHintText || '查看当前索引与队列运行状态。' }}
              </p>
            </div>

            <div class="RuntimeSnapshot-item">
              <div class="RuntimeSnapshot-label">{{ advancedCopy?.searchDatabaseLabel || '当前数据库' }}</div>
              <div class="RuntimeSnapshot-value">
                {{ searchIndexStatus?.databaseLabel || advancedCopy?.searchStatusLoadingText || '加载中...' }}
              </div>
            </div>

            <div class="RuntimeSnapshot-item">
              <div class="RuntimeSnapshot-label">{{ advancedCopy?.searchLastRebuildLabel || '最近重建' }}</div>
              <div class="RuntimeSnapshot-value">
                {{ formatSearchRebuildTime(searchIndexStatus?.lastRebuild?.created_at) }}
              </div>
              <p v-if="searchIndexStatus?.lastRebuild?.duration_ms" class="RuntimeSnapshot-help">
                {{ formatSearchRebuildDuration(searchIndexStatus.lastRebuild.duration_ms) }}
              </p>
            </div>

            <div class="RuntimeSnapshot-item">
              <div class="RuntimeSnapshot-label">{{ advancedCopy?.searchQueueStatusLabel || '索引队列状态' }}</div>
              <div class="RuntimeSnapshot-value">
                {{ searchIndexStatus?.queueWorkerLabel || advancedCopy?.searchStatusLoadingText || '加载中...' }}
              </div>
              <p class="RuntimeSnapshot-help">
                {{ searchIndexStatus?.queueWorkerMessage || advancedCopy?.searchQueueStatusHelpText || '当前重建按钮仍是请求内执行，后续异步索引任务会复用这里的队列运行状态。' }}
              </p>
            </div>
          </div>

          <div
            v-if="Array.isArray(searchIndexStatus?.missing_indexes) && searchIndexStatus.missing_indexes.length > 0"
            class="RuntimeSnapshot-tags"
          >
            <span class="RuntimeSnapshot-tagsLabel">{{ advancedCopy?.searchMissingIndexesLabel || '缺失索引' }}</span>
            <code
              v-for="indexName in searchIndexStatus.missing_indexes"
              :key="indexName"
              class="RuntimeSnapshot-tag"
            >
              {{ indexName }}
            </code>
          </div>
        </div>

        <div class="Form-group">
          <label>{{ advancedCopy?.searchIndexLabel || 'PostgreSQL 全文索引' }}</label>
          <p class="Form-help">{{ advancedCopy?.searchIndexHelpText || '用于英文、数字关键词的讨论、回复和用户搜索。数据量较大时请在低峰期执行。' }}</p>
        </div>

        <AdminInlineMessage v-if="searchIndexStatusError" tone="danger">
          {{ searchIndexStatusError }}
        </AdminInlineMessage>

        <div class="Form-actions">
          <button
            type="button"
            class="Button"
            :disabled="rebuildingSearchIndexes || searchIndexStatus?.supported === false"
            @click="rebuildSearchIndexes"
          >
            {{ rebuildingSearchIndexes ? (advancedCopy?.rebuildingSearchIndexesLabel || '重建中...') : (advancedCopy?.rebuildSearchIndexesLabel || '重建搜索索引') }}
          </button>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.queueSectionTitle || '队列设置' }}</h3>

        <div class="Form-group">
          <label for="advanced-queue-driver">{{ advancedCopy?.queueDriverLabel || '队列驱动' }}</label>
          <select
            id="advanced-queue-driver"
            v-model="settings.queue_driver"
            name="queue_driver"
            class="FormControl"
          >
            <option v-for="option in queueDriverOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <p class="Form-help">{{ advancedCopy?.queueDriverHelpText || '当前通知实时投递已接入统一队列入口。选择 Redis 并部署 worker 后会尝试异步投递。' }}</p>
        </div>

        <div class="Form-group">
          <label>
            <input
              id="advanced-queue-enabled"
              v-model="settings.queue_enabled"
              name="queue_enabled"
              type="checkbox"
              class="FormControl-checkbox"
            />
            {{ advancedCopy?.queueEnabledLabel || '启用队列处理' }}
          </label>
          <p class="Form-help">{{ advancedCopy?.queueEnabledHelpText || '关闭时强制同步执行。开启后，已接入任务会入队执行；入队失败时会同步回退，避免影响主流程。' }}</p>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.humanVerificationSectionTitle || '安全与真人验证' }}</h3>

        <div class="Form-group">
          <label for="advanced-human-verification-provider">{{ advancedCopy?.humanVerificationProviderLabel || '验证提供方' }}</label>
          <select
            id="advanced-human-verification-provider"
            v-model="settings.auth_human_verification_provider"
            name="auth_human_verification_provider"
            class="FormControl"
          >
            <option v-for="option in humanVerificationProviderOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <p class="Form-help">{{ advancedCopy?.humanVerificationProviderHelpText || '建议正式环境开启，优先拦截登录和注册机器人。' }}</p>
        </div>

        <template v-if="settings.auth_human_verification_provider === 'turnstile'">
          <div class="Form-grid">
            <div class="Form-group">
              <label for="advanced-turnstile-site-key">{{ advancedCopy?.turnstileSiteKeyLabel || 'Site Key' }}</label>
              <input
                id="advanced-turnstile-site-key"
                v-model="settings.auth_turnstile_site_key"
                name="auth_turnstile_site_key"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.turnstileSiteKey || '0x4AAAA...'"
              />
            </div>

            <div class="Form-group">
              <label for="advanced-turnstile-secret-key">{{ advancedCopy?.turnstileSecretKeyLabel || 'Secret Key' }}</label>
              <input
                id="advanced-turnstile-secret-key"
                v-model="settings.auth_turnstile_secret_key"
                name="auth_turnstile_secret_key"
                type="password"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.turnstileSecretKey || '0x4AAAA...'"
              />
            </div>
          </div>

          <div class="Form-grid">
            <div class="Form-group Form-group--checkbox">
              <label>
                <input
                  id="advanced-human-verification-login-enabled"
                  v-model="settings.auth_human_verification_login_enabled"
                  name="auth_human_verification_login_enabled"
                  type="checkbox"
                  class="FormControl-checkbox"
                />
                {{ advancedCopy?.turnstileLoginEnabledLabel || '登录时启用真人验证' }}
              </label>
            </div>

            <div class="Form-group Form-group--checkbox">
              <label>
                <input
                  id="advanced-human-verification-register-enabled"
                  v-model="settings.auth_human_verification_register_enabled"
                  name="auth_human_verification_register_enabled"
                  type="checkbox"
                  class="FormControl-checkbox"
                />
                {{ advancedCopy?.turnstileRegisterEnabledLabel || '注册时启用真人验证' }}
              </label>
            </div>
          </div>

          <p v-if="turnstileMisconfigured" class="Form-warning">
            {{ advancedCopy?.turnstileMisconfiguredText || '已选择 Turnstile，但 Site Key 或 Secret Key 仍为空，当前不会真正启用验证。' }}
          </p>
        </template>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.storageSectionTitle || '文件存储' }}</h3>

        <div class="Form-group">
          <label for="advanced-storage-driver">{{ advancedCopy?.storageDriverLabel || '存储驱动' }}</label>
          <select
            id="advanced-storage-driver"
            v-model="settings.storage_driver"
            name="storage_driver"
            class="FormControl"
          >
            <option v-for="option in storageDriverOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <p class="Form-help">{{ advancedCopy?.storageDriverHelpText || 'Composer 上传、头像上传和后续附件能力都会读取这里的运行时配置' }}</p>
        </div>

        <div class="Form-grid">
          <div class="Form-group">
            <label for="advanced-storage-attachments-dir">{{ advancedCopy?.storageAttachmentsDirLabel || '附件目录' }}</label>
            <input
              id="advanced-storage-attachments-dir"
              v-model="settings.storage_attachments_dir"
              name="storage_attachments_dir"
              type="text"
              class="FormControl"
              :placeholder="advancedConfig?.placeholders?.storageAttachmentsDir || 'attachments'"
            />
            <p class="Form-help">{{ advancedCopy?.storageAttachmentsDirHelpText || '统一的附件对象目录，支持多级路径' }}</p>
          </div>

          <div class="Form-group">
            <label for="advanced-storage-avatars-dir">{{ advancedCopy?.storageAvatarsDirLabel || '头像目录' }}</label>
            <input
              id="advanced-storage-avatars-dir"
              v-model="settings.storage_avatars_dir"
              name="storage_avatars_dir"
              type="text"
              class="FormControl"
              :placeholder="advancedConfig?.placeholders?.storageAvatarsDir || 'avatars'"
            />
            <p class="Form-help">{{ advancedCopy?.storageAvatarsDirHelpText || '头像和缩略图的对象目录' }}</p>
          </div>
        </div>

        <div class="Form-section Form-section--nested">
          <div class="Form-sectionHeader">
            <h4>{{ advancedCopy?.uploadPolicyTitle || '上传策略' }}</h4>
            <p>{{ advancedCopy?.uploadPolicyDescription || '限制上传大小，扩展名白名单仍由服务端固定控制。' }}</p>
          </div>

          <div class="Form-grid">
            <div class="Form-group">
              <label for="advanced-upload-avatar-max-size">{{ advancedCopy?.uploadAvatarMaxSizeLabel || '头像最大体积（MB）' }}</label>
              <input
                id="advanced-upload-avatar-max-size"
                v-model.number="settings.upload_avatar_max_size_mb"
                name="upload_avatar_max_size_mb"
                type="number"
                min="1"
                max="100"
                class="FormControl"
              />
            </div>

            <div class="Form-group">
              <label for="advanced-upload-attachment-max-size">{{ advancedCopy?.uploadAttachmentMaxSizeLabel || '附件最大体积（MB）' }}</label>
              <input
                id="advanced-upload-attachment-max-size"
                v-model.number="settings.upload_attachment_max_size_mb"
                name="upload_attachment_max_size_mb"
                type="number"
                min="1"
                max="100"
                class="FormControl"
              />
            </div>

            <div class="Form-group">
              <label for="advanced-upload-site-asset-max-size">{{ advancedCopy?.uploadSiteAssetMaxSizeLabel || '站点资源最大体积（MB）' }}</label>
              <input
                id="advanced-upload-site-asset-max-size"
                v-model.number="settings.upload_site_asset_max_size_mb"
                name="upload_site_asset_max_size_mb"
                type="number"
                min="1"
                max="100"
                class="FormControl"
              />
            </div>
          </div>

          <p class="Form-help">{{ advancedCopy?.uploadSizeHelpText || '头像默认 2MB，Composer 附件默认 10MB，Logo/Favicon 默认 2MB。' }}</p>
        </div>

        <template v-if="settings.storage_driver === 'local'">
          <div class="Form-grid">
            <div class="Form-group">
              <label for="advanced-storage-local-path">{{ advancedCopy?.localPathLabel || '本地保存目录' }}</label>
              <input
                id="advanced-storage-local-path"
                v-model="settings.storage_local_path"
                name="storage_local_path"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageLocalPath || 'D:\\data\\bias\\media'"
              />
              <p class="Form-help">{{ advancedCopy?.localPathHelpText || '可填写绝对路径，也可填写相对项目根目录的路径' }}</p>
            </div>

            <div class="Form-group">
              <label for="advanced-storage-local-base-url">{{ advancedCopy?.localBaseUrlLabel || '本地访问基地址' }}</label>
              <input
                id="advanced-storage-local-base-url"
                v-model="settings.storage_local_base_url"
                name="storage_local_base_url"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageLocalBaseUrl || '/media/'"
              />
              <p class="Form-help">{{ advancedCopy?.localBaseUrlHelpText || '上传完成后生成给前台的 URL 前缀' }}</p>
            </div>
          </div>
        </template>

        <template v-if="settings.storage_driver === 's3'">
          <div class="Form-grid">
            <div class="Form-group">
              <label for="advanced-storage-s3-bucket">{{ advancedCopy?.bucketLabel || 'Bucket' }}</label>
              <input
                id="advanced-storage-s3-bucket"
                v-model="settings.storage_s3_bucket"
                name="storage_s3_bucket"
                type="text"
                class="FormControl"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-s3-region">{{ advancedCopy?.regionLabel || 'Region' }}</label>
              <input
                id="advanced-storage-s3-region"
                v-model="settings.storage_s3_region"
                name="storage_s3_region"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageS3Region || 'ap-southeast-1'"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-s3-endpoint">{{ advancedCopy?.endpointLabel || 'Endpoint' }}</label>
              <input
                id="advanced-storage-s3-endpoint"
                v-model="settings.storage_s3_endpoint"
                name="storage_s3_endpoint"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageS3Endpoint || 'https://s3.amazonaws.com'"
              />
              <p class="Form-help">{{ advancedCopy?.s3EndpointHelpText || '使用 MinIO、Wasabi 等兼容服务时填写自定义 Endpoint' }}</p>
            </div>
            <div class="Form-group">
              <label for="advanced-storage-s3-public-url">{{ advancedCopy?.publicUrlLabel || '公共访问 URL' }}</label>
              <input
                id="advanced-storage-s3-public-url"
                v-model="settings.storage_s3_public_url"
                name="storage_s3_public_url"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageS3PublicUrl || 'https://cdn.example.com'"
              />
              <p class="Form-help">{{ advancedCopy?.s3PublicUrlHelpText || '如留空，系统会按标准 S3 域名尝试拼接' }}</p>
            </div>
            <div class="Form-group">
              <label for="advanced-storage-s3-access-key-id">{{ advancedCopy?.accessKeyIdLabel || 'Access Key ID' }}</label>
              <input
                id="advanced-storage-s3-access-key-id"
                v-model="settings.storage_s3_access_key_id"
                name="storage_s3_access_key_id"
                type="text"
                class="FormControl"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-s3-secret-access-key">{{ advancedCopy?.secretAccessKeyLabel || 'Secret Access Key' }}</label>
              <input
                id="advanced-storage-s3-secret-access-key"
                v-model="settings.storage_s3_secret_access_key"
                name="storage_s3_secret_access_key"
                type="password"
                class="FormControl"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-s3-object-prefix">{{ advancedCopy?.objectPrefixLabel || '对象前缀' }}</label>
              <input
                id="advanced-storage-s3-object-prefix"
                v-model="settings.storage_s3_object_prefix"
                name="storage_s3_object_prefix"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageObjectPrefix || 'bias'"
              />
            </div>
            <div class="Form-group Form-group--checkbox">
              <label>
                <input
                  id="advanced-storage-s3-path-style"
                  v-model="settings.storage_s3_path_style"
                  name="storage_s3_path_style"
                  type="checkbox"
                  class="FormControl-checkbox"
                />
                {{ advancedCopy?.pathStyleLabel || '使用 Path Style' }}
              </label>
              <p class="Form-help">{{ advancedCopy?.pathStyleHelpText || '兼容部分 S3 服务或自建对象存储' }}</p>
            </div>
          </div>
        </template>

        <template v-if="settings.storage_driver === 'r2'">
          <div class="Form-grid">
            <div class="Form-group">
              <label for="advanced-storage-r2-bucket">{{ advancedCopy?.bucketLabel || 'Bucket' }}</label>
              <input
                id="advanced-storage-r2-bucket"
                v-model="settings.storage_r2_bucket"
                name="storage_r2_bucket"
                type="text"
                class="FormControl"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-r2-endpoint">{{ advancedCopy?.endpointLabel || 'Endpoint' }}</label>
              <input
                id="advanced-storage-r2-endpoint"
                v-model="settings.storage_r2_endpoint"
                name="storage_r2_endpoint"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageR2Endpoint || 'https://<accountid>.r2.cloudflarestorage.com'"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-r2-public-url">{{ advancedCopy?.publicUrlCdnLabel || '公共访问 URL / CDN 域名' }}</label>
              <input
                id="advanced-storage-r2-public-url"
                v-model="settings.storage_r2_public_url"
                name="storage_r2_public_url"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageR2PublicUrl || 'https://pub-xxx.r2.dev'"
              />
              <p class="Form-help">{{ advancedCopy?.r2PublicUrlHelpText || 'R2 通常需要单独的公开域名，否则前台生成的附件链接不可访问' }}</p>
            </div>
            <div class="Form-group">
              <label for="advanced-storage-r2-access-key-id">{{ advancedCopy?.accessKeyIdLabel || 'Access Key ID' }}</label>
              <input
                id="advanced-storage-r2-access-key-id"
                v-model="settings.storage_r2_access_key_id"
                name="storage_r2_access_key_id"
                type="text"
                class="FormControl"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-r2-secret-access-key">{{ advancedCopy?.secretAccessKeyLabel || 'Secret Access Key' }}</label>
              <input
                id="advanced-storage-r2-secret-access-key"
                v-model="settings.storage_r2_secret_access_key"
                name="storage_r2_secret_access_key"
                type="password"
                class="FormControl"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-r2-object-prefix">{{ advancedCopy?.objectPrefixLabel || '对象前缀' }}</label>
              <input
                id="advanced-storage-r2-object-prefix"
                v-model="settings.storage_r2_object_prefix"
                name="storage_r2_object_prefix"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageObjectPrefix || 'bias'"
              />
            </div>
          </div>
        </template>

        <template v-if="settings.storage_driver === 'oss'">
          <div class="Form-grid">
            <div class="Form-group">
              <label for="advanced-storage-oss-bucket">{{ advancedCopy?.bucketLabel || 'Bucket' }}</label>
              <input
                id="advanced-storage-oss-bucket"
                v-model="settings.storage_oss_bucket"
                name="storage_oss_bucket"
                type="text"
                class="FormControl"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-oss-endpoint">{{ advancedCopy?.endpointLabel || 'Endpoint' }}</label>
              <input
                id="advanced-storage-oss-endpoint"
                v-model="settings.storage_oss_endpoint"
                name="storage_oss_endpoint"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageOssEndpoint || 'oss-cn-hangzhou.aliyuncs.com'"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-oss-public-url">{{ advancedCopy?.publicUrlLabel || '公共访问 URL' }}</label>
              <input
                id="advanced-storage-oss-public-url"
                v-model="settings.storage_oss_public_url"
                name="storage_oss_public_url"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageS3PublicUrl || 'https://cdn.example.com'"
              />
              <p class="Form-help">{{ advancedCopy?.ossPublicUrlHelpText || '如留空，将按 Bucket + Endpoint 生成标准 OSS 访问地址' }}</p>
            </div>
            <div class="Form-group">
              <label for="advanced-storage-oss-access-key-id">{{ advancedCopy?.accessKeyIdLabel || 'Access Key ID' }}</label>
              <input
                id="advanced-storage-oss-access-key-id"
                v-model="settings.storage_oss_access_key_id"
                name="storage_oss_access_key_id"
                type="text"
                class="FormControl"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-oss-access-key-secret">{{ advancedCopy?.accessKeySecretLabel || 'Access Key Secret' }}</label>
              <input
                id="advanced-storage-oss-access-key-secret"
                v-model="settings.storage_oss_access_key_secret"
                name="storage_oss_access_key_secret"
                type="password"
                class="FormControl"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-oss-object-prefix">{{ advancedCopy?.objectPrefixLabel || '对象前缀' }}</label>
              <input
                id="advanced-storage-oss-object-prefix"
                v-model="settings.storage_oss_object_prefix"
                name="storage_oss_object_prefix"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.storageObjectPrefix || 'bias'"
              />
            </div>
          </div>
        </template>

        <template v-if="settings.storage_driver === 'imagebed'">
          <div class="Form-grid">
            <div class="Form-group">
              <label for="advanced-storage-imagebed-endpoint">{{ advancedCopy?.imagebedEndpointLabel || '上传接口地址' }}</label>
              <input
                id="advanced-storage-imagebed-endpoint"
                v-model="settings.storage_imagebed_endpoint"
                name="storage_imagebed_endpoint"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.imagebedEndpoint || 'https://example.com/api/upload'"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-imagebed-method">{{ advancedCopy?.imagebedMethodLabel || '请求方法' }}</label>
              <select
                id="advanced-storage-imagebed-method"
                v-model="settings.storage_imagebed_method"
                name="storage_imagebed_method"
                class="FormControl"
              >
                <option v-for="option in imagebedMethodOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>
            <div class="Form-group">
              <label for="advanced-storage-imagebed-file-field">{{ advancedCopy?.imagebedFileFieldLabel || '文件字段名' }}</label>
              <input
                id="advanced-storage-imagebed-file-field"
                v-model="settings.storage_imagebed_file_field"
                name="storage_imagebed_file_field"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.imagebedFileField || 'file'"
              />
            </div>
            <div class="Form-group">
              <label for="advanced-storage-imagebed-url-path">{{ advancedCopy?.imagebedUrlPathLabel || '响应 URL 路径' }}</label>
              <input
                id="advanced-storage-imagebed-url-path"
                v-model="settings.storage_imagebed_url_path"
                name="storage_imagebed_url_path"
                type="text"
                class="FormControl"
                :placeholder="advancedConfig?.placeholders?.imagebedUrlPath || 'data.url'"
              />
              <p class="Form-help">{{ advancedCopy?.imagebedUrlPathHelpText || '支持点路径，例如 `data.url`、`result.images.0.url`' }}</p>
            </div>
          </div>

          <div class="Form-group">
            <label for="advanced-storage-imagebed-headers">{{ advancedCopy?.imagebedHeadersLabel || '请求头 JSON' }}</label>
            <textarea
              id="advanced-storage-imagebed-headers"
              v-model="settings.storage_imagebed_headers"
              name="storage_imagebed_headers"
              class="FormControl"
              rows="4"
              :placeholder="advancedConfig?.placeholders?.imagebedHeaders || '{&quot;Authorization&quot;:&quot;Bearer token&quot;}'"
            ></textarea>
          </div>

          <div class="Form-group">
            <label for="advanced-storage-imagebed-form-data">{{ advancedCopy?.imagebedFormDataLabel || '额外表单参数 JSON' }}</label>
            <textarea
              id="advanced-storage-imagebed-form-data"
              v-model="settings.storage_imagebed_form_data"
              name="storage_imagebed_form_data"
              class="FormControl"
              rows="4"
              :placeholder="advancedConfig?.placeholders?.imagebedFormData || '{&quot;album&quot;:&quot;forum&quot;}'"
            ></textarea>
          </div>
        </template>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.maintenanceSectionTitle || '维护模式' }}</h3>

        <div class="Form-group">
          <label>
            <input
              id="advanced-maintenance-mode"
              v-model="settings.maintenance_mode"
              name="maintenance_mode"
              type="checkbox"
              class="FormControl-checkbox"
            />
            {{ advancedCopy?.maintenanceEnabledLabel || '启用维护模式' }}
          </label>
          <p class="Form-help">{{ advancedCopy?.maintenanceEnabledHelpText || '启用后，普通用户访问论坛 API 将收到 503；`/api/forum`、登录接口和后台入口保留豁免。' }}</p>
        </div>

        <div class="Form-group">
          <label for="advanced-maintenance-message">{{ advancedCopy?.maintenanceMessageLabel || '维护提示信息' }}</label>
          <textarea
            id="advanced-maintenance-message"
            v-model="settings.maintenance_message"
            name="maintenance_message"
            class="FormControl"
            rows="3"
            :placeholder="advancedConfig?.placeholders?.maintenanceMessage || '论坛正在维护中，请稍后再试...'"
          ></textarea>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">{{ advancedCopy?.debugSectionTitle || '调试设置' }}</h3>

        <div class="Form-group">
          <label>
            <input
              id="advanced-debug-mode"
              v-model="settings.debug_mode"
              name="debug_mode"
              type="checkbox"
              class="FormControl-checkbox"
              disabled
            />
            {{ advancedCopy?.debugModeLabel || '调试模式（只读）' }}
          </label>
          <p class="Form-help">{{ advancedCopy?.debugModeHelpText || '当前运行值来自 Django 配置文件或环境变量，保存这里不会热切换服务端 DEBUG。' }}</p>
        </div>

        <div class="Form-group">
          <label>
            <input
              id="advanced-log-queries"
              v-model="settings.log_queries"
              name="log_queries"
              type="checkbox"
              class="FormControl-checkbox"
            />
            {{ advancedCopy?.logQueriesLabel || '记录数据库查询' }}
          </label>
          <p class="Form-help">{{ advancedCopy?.logQueriesHelpText || '保存后即时生效。会把每个 HTTP 请求触发的 SQL 记录到服务器日志。' }}</p>
        </div>
      </div>

      <div class="Form-actions">
        <button
          type="button"
          class="Button Button--primary"
          :disabled="saving"
          @click="saveSettings"
        >
          {{ saving ? (advancedCopy?.savingLabel || '保存中...') : (advancedCopy?.saveLabel || '保存设置') }}
        </button>
      </div>
      <AdminInlineMessage v-if="saveSuccess" tone="success">{{ advancedCopy?.saveSuccessText || '保存成功' }}</AdminInlineMessage>
      <AdminInlineMessage v-if="saveError" tone="danger">{{ saveErrorMessage || advancedCopy?.saveErrorText || '保存失败，请重试' }}</AdminInlineMessage>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminPage from '../components/AdminPage.vue'
import { useAdminSaveFeedback } from '../composables/useAdminSaveFeedback'
import api from '../../api'
import { useModalStore } from '../../stores/modal'
import {
  getAdminAdvancedPageActionMeta,
  getAdminAdvancedPageConfig,
  getAdminAdvancedPageCopy,
} from '../registry'

const advancedCopy = computed(() => getAdminAdvancedPageCopy())
const advancedConfig = computed(() => getAdminAdvancedPageConfig())
const advancedActionMeta = computed(() => getAdminAdvancedPageActionMeta())
const settings = ref({})
const searchIndexStatus = ref(null)
const searchIndexStatusError = ref('')

const saving = ref(false)
const clearing = ref(false)
const rebuildingSearchIndexes = ref(false)
const loadedSettingsSnapshot = ref(null)
const modalStore = useModalStore()
const { saveSuccess, saveError, saveErrorMessage, resetSaveFeedback, showSaveSuccess, showSaveError } = useAdminSaveFeedback()
const cacheDriverOptions = computed(() => advancedConfig.value?.cacheDriverOptions || [])
const queueDriverOptions = computed(() => advancedConfig.value?.queueDriverOptions || [])
const humanVerificationProviderOptions = computed(() => advancedConfig.value?.humanVerificationProviderOptions || [])
const storageDriverOptions = computed(() => advancedConfig.value?.storageDriverOptions || [])
const imagebedMethodOptions = computed(() => advancedConfig.value?.imagebedMethodOptions || [])
const turnstileMisconfigured = computed(() => (
  settings.value.auth_human_verification_provider === 'turnstile'
  && (!settings.value.auth_turnstile_site_key || !settings.value.auth_turnstile_secret_key)
))

function defaultSettings() {
  return {
    cache_driver: 'file',
    cache_lifetime: 3600,
    queue_driver: 'sync',
    queue_enabled: false,
    maintenance_mode: false,
    maintenance_message: '',
    debug_mode: false,
    log_queries: false,
    auth_human_verification_provider: 'off',
    auth_turnstile_site_key: '',
    auth_turnstile_secret_key: '',
    auth_human_verification_login_enabled: true,
    auth_human_verification_register_enabled: true,
    storage_driver: 'local',
    storage_attachments_dir: 'attachments',
    storage_avatars_dir: 'avatars',
    upload_avatar_max_size_mb: 2,
    upload_attachment_max_size_mb: 10,
    upload_site_asset_max_size_mb: 2,
    storage_local_path: '',
    storage_local_base_url: '/media/',
    storage_s3_bucket: '',
    storage_s3_region: '',
    storage_s3_endpoint: '',
    storage_s3_access_key_id: '',
    storage_s3_secret_access_key: '',
    storage_s3_public_url: '',
    storage_s3_object_prefix: '',
    storage_s3_path_style: false,
    storage_r2_bucket: '',
    storage_r2_endpoint: '',
    storage_r2_access_key_id: '',
    storage_r2_secret_access_key: '',
    storage_r2_public_url: '',
    storage_r2_object_prefix: '',
    storage_oss_bucket: '',
    storage_oss_endpoint: '',
    storage_oss_access_key_id: '',
    storage_oss_access_key_secret: '',
    storage_oss_public_url: '',
    storage_oss_object_prefix: '',
    storage_imagebed_endpoint: '',
    storage_imagebed_method: 'POST',
    storage_imagebed_file_field: 'file',
    storage_imagebed_headers: '{}',
    storage_imagebed_form_data: '{}',
    storage_imagebed_url_path: 'data.url',
    ...(advancedConfig.value?.defaultSettings || {}),
  }
}

onMounted(async () => {
  settings.value = defaultSettings()
  await Promise.all([
    loadAdvancedSettings(),
    loadSearchIndexStatus(),
  ])
})

async function loadAdvancedSettings() {
  try {
    const data = await api.get('/admin/advanced')
    settings.value = { ...settings.value, ...data }
    loadedSettingsSnapshot.value = createSettingsSnapshot(settings.value)
  } catch (error) {
    console.error('加载高级设置失败:', error)
  }
}

async function loadSearchIndexStatus() {
  searchIndexStatusError.value = ''
  try {
    searchIndexStatus.value = await api.get('/admin/search-indexes/status')
  } catch (error) {
    console.error('加载搜索索引状态失败:', error)
    searchIndexStatusError.value = error.response?.data?.error
      || advancedActionMeta.value?.loadSearchStatusErrorText
      || '加载搜索索引状态失败，请稍后重试'
  }
}

async function saveSettings() {
  const sensitiveChanges = getSensitiveSettingChanges()
  if (sensitiveChanges.length > 0) {
    const confirmed = await modalStore.confirm({
      title: advancedActionMeta.value?.saveConfirmTitle || '保存高级设置',
      message: advancedActionMeta.value?.saveConfirmMessage?.(sensitiveChanges) || `以下设置会影响运行时行为：${sensitiveChanges.join('、')}。确定保存当前配置吗？`,
      confirmText: advancedActionMeta.value?.saveConfirmText || '保存',
      cancelText: advancedActionMeta.value?.saveCancelText || '取消',
      tone: 'warning'
    })
    if (!confirmed) {
      return
    }
  }

  saving.value = true
  resetSaveFeedback()

  try {
    const response = await api.post('/admin/advanced', settings.value)
    if (response?.settings) {
      settings.value = { ...settings.value, ...response.settings }
    }
    loadedSettingsSnapshot.value = createSettingsSnapshot(settings.value)
    showSaveSuccess()
  } catch (error) {
    console.error('保存高级设置失败:', error)
    showSaveError(error.response?.data?.message || error.response?.data?.error || '')
  } finally {
    saving.value = false
  }
}

async function clearCache() {
  const confirmed = await modalStore.confirm({
    title: advancedActionMeta.value?.clearCacheConfirmTitle || '清除缓存',
    message: advancedActionMeta.value?.clearCacheConfirmMessage || '确定清除运行时缓存吗？短时间内部分页面可能重新读取配置和数据。',
    confirmText: advancedActionMeta.value?.clearCacheConfirmText || '清除',
    cancelText: advancedActionMeta.value?.clearCacheCancelText || '取消',
    tone: 'warning'
  })
  if (!confirmed) {
    return
  }

  clearing.value = true
  try {
    await api.post('/admin/cache/clear')
    await modalStore.alert({
      title: advancedActionMeta.value?.clearCacheSuccessTitle || '缓存已清除',
      message: advancedActionMeta.value?.clearCacheSuccessMessage || '运行时缓存已成功清理。',
      tone: 'success'
    })
  } catch (error) {
    await modalStore.alert({
      title: advancedActionMeta.value?.clearCacheFailedTitle || '清除缓存失败',
      message: error.response?.data?.error || error.message || advancedActionMeta.value?.unknownErrorText || '未知错误',
      tone: 'danger'
    })
  } finally {
    clearing.value = false
  }
}

async function rebuildSearchIndexes() {
  const confirmed = await modalStore.confirm({
    title: advancedActionMeta.value?.rebuildSearchConfirmTitle || '重建搜索索引',
    message: advancedActionMeta.value?.rebuildSearchConfirmMessage || '确定在后台重建 PostgreSQL 全文搜索索引吗？数据量较大时可能耗时较长，建议在低峰期执行。',
    confirmText: advancedActionMeta.value?.rebuildSearchConfirmText || '重建',
    cancelText: advancedActionMeta.value?.rebuildSearchCancelText || '取消',
    tone: 'warning'
  })
  if (!confirmed) {
    return
  }

  rebuildingSearchIndexes.value = true
  try {
    const response = await api.post('/admin/search-indexes/rebuild')
    await loadSearchIndexStatus()
    await modalStore.alert({
      title: advancedActionMeta.value?.rebuildSearchSuccessTitle || '搜索索引已重建',
      message: advancedActionMeta.value?.rebuildSearchSuccessMessage?.(response) || '已重建讨论、回复和用户搜索索引。',
      tone: 'success'
    })
  } catch (error) {
    await modalStore.alert({
      title: advancedActionMeta.value?.rebuildSearchFailedTitle || '重建搜索索引失败',
      message: error.response?.data?.error || error.message || advancedActionMeta.value?.unknownErrorText || '未知错误',
      tone: 'danger'
    })
  } finally {
    rebuildingSearchIndexes.value = false
  }
}

function createSettingsSnapshot(value) {
  return {
    maintenance_mode: Boolean(value.maintenance_mode),
    queue_enabled: Boolean(value.queue_enabled),
    queue_driver: value.queue_driver,
    log_queries: Boolean(value.log_queries),
    storage_driver: value.storage_driver,
    upload_avatar_max_size_mb: normalizeUploadSize(value.upload_avatar_max_size_mb),
    upload_attachment_max_size_mb: normalizeUploadSize(value.upload_attachment_max_size_mb),
    upload_site_asset_max_size_mb: normalizeUploadSize(value.upload_site_asset_max_size_mb),
  }
}

function getSensitiveSettingChanges() {
  const previous = loadedSettingsSnapshot.value
  if (!previous) {
    return []
  }

  const current = createSettingsSnapshot(settings.value)
  const labels = advancedConfig.value?.sensitiveLabels || {}

  return Object.keys(labels).filter(key => previous[key] !== current[key]).map(key => labels[key])
}

function normalizeUploadSize(value) {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed)) {
    return 1
  }
  return Math.min(100, Math.max(1, parsed))
}

function formatSearchRebuildTime(value) {
  if (!value) {
    return advancedCopy.value?.searchNeverRebuiltText || '尚未重建'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatSearchRebuildDuration(durationMs) {
  const normalized = Number(durationMs || 0)
  if (!normalized) {
    return advancedCopy.value?.searchLastRebuildDurationFallback || '最近一次重建未记录耗时。'
  }
  return advancedCopy.value?.searchLastRebuildDurationText?.(normalized) || `最近一次耗时 ${normalized} ms`
}
</script>

<style scoped>
.AdvancedPage-content {
  max-width: 920px;
}

.RuntimeNotice {
  background: linear-gradient(135deg, var(--forum-bg-elevated-strong) 0%, var(--forum-bg-subtle) 100%);
  border: 1px solid var(--forum-border-color);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: var(--forum-shadow-sm);
}

.RuntimeNotice-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.RuntimeNotice h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--forum-text-color);
}

.RuntimeNotice p {
  margin: 0;
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
  line-height: 1.7;
}

.Section-title {
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--forum-border-soft);
}

.RuntimeSnapshot {
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 12px;
  background: linear-gradient(180deg, var(--forum-bg-elevated) 0%, var(--forum-bg-subtle) 100%);
}

.RuntimeSnapshot-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.RuntimeSnapshot-item {
  min-width: 0;
}

.RuntimeSnapshot-label {
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--forum-text-muted);
}

.RuntimeSnapshot-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--forum-text-color);
  word-break: break-word;
}

.RuntimeSnapshot-help {
  margin: 6px 0 0;
  font-size: var(--forum-font-size-sm);
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.RuntimeSnapshot-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.RuntimeSnapshot-tagsLabel {
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
}

.RuntimeSnapshot-tag {
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--forum-bg-subtle);
  border: 1px solid var(--forum-border-color);
  font-size: 12px;
}

.Form-grid {
  gap: 0 16px;
}

.Form-group--checkbox label {
  margin-bottom: 6px;
}

.Form-section--nested {
  margin: 4px 0 22px;
  padding: 16px;
  background: var(--forum-bg-elevated-strong);
  box-shadow: none;
}

.Form-section--nested .Form-sectionHeader {
  margin-bottom: 14px;
}

.Form-section--nested h4 {
  margin: 0 0 6px;
  color: var(--forum-text-color);
  font-size: 15px;
}

.Form-section--nested p {
  margin: 0;
}

.Form-warning {
  margin: 0;
  color: var(--forum-warning-color);
  font-size: var(--forum-font-size-sm);
  line-height: 1.6;
}

@media (max-width: 768px) {
  .RuntimeNotice-grid,
  .RuntimeSnapshot-grid,
  .Form-grid {
    grid-template-columns: 1fr;
  }

  .AdvancedPage-content {
    max-width: none;
  }

  .RuntimeNotice {
    padding: 16px;
    border-radius: 14px;
  }
}
</style>
