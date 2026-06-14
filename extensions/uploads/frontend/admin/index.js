import { extendAdmin } from '@bias/admin'

const ADVANCED_PAGE_KEY = 'core.advanced'
const APPEARANCE_PAGE_KEY = 'core.appearance'

export const extend = [
  extendAdmin(admin => admin
    .pageCopy(ADVANCED_PAGE_KEY, {
      key: 'uploads-advanced-copy',
      moduleId: 'uploads',
      order: 30,
      resolve: () => ({
        storageSectionTitle: '文件存储',
        storageDriverLabel: '存储驱动',
        storageDriverHelpText: '上传扩展、头像和附件能力都会读取这里的运行时存储配置。',
        storageObjectDirectoryHelpText: '附件和头像对象目录由对应扩展管理。',
        uploadPolicyTitle: '上传策略',
        uploadPolicyDescription: '限制核心站点资源上传大小；头像和附件上传策略由对应扩展管理。',
        uploadSiteAssetMaxSizeLabel: '站点资源最大体积（MB）',
        uploadSizeHelpText: 'Logo/Favicon 默认 2MB。',
        localPathLabel: '本地保存目录',
        localPathHelpText: '可填写绝对路径，也可填写相对项目根目录的路径',
        localBaseUrlLabel: '本地访问基地址',
        localBaseUrlHelpText: '上传完成后生成给前台的 URL 前缀',
        bucketLabel: 'Bucket',
        regionLabel: 'Region',
        endpointLabel: 'Endpoint',
        publicUrlLabel: '公共访问 URL',
        publicUrlCdnLabel: '公共访问 URL / CDN 域名',
        s3EndpointHelpText: '使用 MinIO、Wasabi 等兼容服务时填写自定义 Endpoint',
        s3PublicUrlHelpText: '如留空，系统会按标准 S3 域名尝试拼接',
        accessKeyIdLabel: 'Access Key ID',
        secretAccessKeyLabel: 'Secret Access Key',
        accessKeySecretLabel: 'Access Key Secret',
        objectPrefixLabel: '对象前缀',
        pathStyleLabel: '使用 Path Style',
        pathStyleHelpText: '兼容部分 S3 服务或自建对象存储',
        r2PublicUrlHelpText: 'R2 通常需要单独的公开域名，否则前台生成的附件链接不可访问',
        ossPublicUrlHelpText: '如留空，将按 Bucket + Endpoint 生成标准 OSS 访问地址',
        imagebedEndpointLabel: '上传接口地址',
        imagebedMethodLabel: '请求方法',
        imagebedFileFieldLabel: '文件字段名',
        imagebedUrlPathLabel: '响应 URL 路径',
        imagebedUrlPathHelpText: '支持点路径，例如 `data.url`、`result.images.0.url`',
        imagebedHeadersLabel: '请求头 JSON',
        imagebedFormDataLabel: '额外表单参数 JSON',
      }),
    })
    .pageConfig(ADVANCED_PAGE_KEY, {
      key: 'uploads-advanced-config',
      moduleId: 'uploads',
      order: 30,
      resolve: () => ({
        enableStorageSection: true,
        enableUploadPolicySection: true,
        defaultSettings: {
          storage_driver: 'local',
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
          upload_site_asset_max_size_mb: 2,
        },
        placeholders: {
          storageLocalPath: 'D:\\data\\bias\\media',
          storageLocalBaseUrl: '/media/',
          storageS3Region: 'ap-southeast-1',
          storageS3Endpoint: 'https://s3.amazonaws.com',
          storageS3PublicUrl: 'https://cdn.example.com',
          storageObjectPrefix: 'bias',
          storageR2Endpoint: 'https://<accountid>.r2.cloudflarestorage.com',
          storageR2PublicUrl: 'https://pub-xxx.r2.dev',
          storageOssEndpoint: 'oss-cn-hangzhou.aliyuncs.com',
          imagebedEndpoint: 'https://example.com/api/upload',
          imagebedFileField: 'file',
          imagebedUrlPath: 'data.url',
          imagebedHeaders: '{\"Authorization\":\"Bearer token\"}',
          imagebedFormData: '{\"album\":\"forum\"}',
        },
        storageDriverOptions: [
          { value: 'local', label: '本地存储' },
          { value: 's3', label: 'Amazon S3 / S3 兼容' },
          { value: 'r2', label: 'Cloudflare R2' },
          { value: 'oss', label: '阿里云 OSS' },
          { value: 'imagebed', label: '通用图床' },
        ],
        imagebedMethodOptions: [
          { value: 'POST', label: 'POST' },
          { value: 'PUT', label: 'PUT' },
          { value: 'PATCH', label: 'PATCH' },
        ],
        sensitiveLabels: {
          storage_driver: '文件存储驱动',
          upload_site_asset_max_size_mb: '站点资源上传上限',
        },
      }),
    }))
  ,
  extendAdmin(admin => admin
    .pageCopy(APPEARANCE_PAGE_KEY, {
      key: 'uploads-appearance-copy',
      moduleId: 'uploads',
      order: 30,
      resolve: () => ({
        logoUploadLabel: '上传本地 Logo',
        logoUploadingLabel: '上传中...',
        faviconUploadLabel: '上传本地 Favicon',
        faviconUploadingLabel: '上传中...',
      }),
    })
    .pageConfig(APPEARANCE_PAGE_KEY, {
      key: 'uploads-appearance-config',
      moduleId: 'uploads',
      order: 30,
      resolve: () => ({
        uploads: {
          logoAccept: '.png,.jpg,.jpeg,.gif,.webp,.svg',
          faviconAccept: '.ico,.png,.svg,.webp',
        },
      }),
    })
    .pageActionMeta(APPEARANCE_PAGE_KEY, {
      key: 'uploads-appearance-action-meta',
      moduleId: 'uploads',
      order: 30,
      resolve: () => ({
        uploadFailedTitle: '上传失败',
        uploadUnknownErrorText: '未知错误',
      }),
    })
    .pageAction(APPEARANCE_PAGE_KEY, {
      key: 'upload-site-asset',
      moduleId: 'uploads',
      order: 10,
      resolve: ({ api, modalStore, appearanceActionMeta, settings, setUploading }) => ({
        run: async ({ file, target }) => {
          setUploading?.(target, true)
          try {
            const formData = new FormData()
            formData.append('file', file)

            const response = await api.post('/admin/appearance/upload', formData, {
              params: { target },
              headers: { 'Content-Type': 'multipart/form-data' },
            })

            if (target === 'logo') {
              settings.logo_url = response.url || ''
            } else {
              settings.favicon_url = response.url || ''
            }
          } catch (error) {
            console.error('上传站点资源失败:', error)
            await modalStore.alert({
              title: appearanceActionMeta?.uploadFailedTitle || '上传失败',
              message: error.response?.data?.error || error.message || appearanceActionMeta?.uploadUnknownErrorText || '未知错误',
              tone: 'danger',
            })
          } finally {
            setUploading?.(target, false)
          }
        },
      }),
    }))
]
