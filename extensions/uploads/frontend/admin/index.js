import { extendAdmin } from '@bias/admin'
import UploadsSettingsPage from './UploadsSettingsPage.vue'

const APPEARANCE_PAGE_KEY = 'core.appearance'
const UPLOADS_PAGE_KEY = 'uploads.settings'

export const extend = [
  extendAdmin(admin => admin
    .pageCopy(UPLOADS_PAGE_KEY, {
      key: 'uploads-settings-copy',
      moduleId: 'uploads',
      order: 30,
      resolve: () => ({
        pageTitle: '上传设置',
        pageDescription: '配置附件、站点资源和存储驱动。',
      }),
    })
    .pageConfig(UPLOADS_PAGE_KEY, {
      key: 'uploads-settings-config',
      moduleId: 'uploads',
      order: 30,
      resolve: () => ({
        defaultSettings: {
          attachments_dir: 'attachments',
          attachment_max_size_mb: 10,
          upload_site_asset_max_size_mb: 2,
          avatars_dir: 'avatars',
          avatar_max_size_mb: 2,
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
          attachmentsDir: 'attachments',
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
          attachments_dir: '附件目录',
          attachment_max_size_mb: '附件最大体积',
          avatars_dir: '头像目录',
          avatar_max_size_mb: '头像最大体积',
          storage_driver: '文件存储驱动',
          storage_local_path: '本地保存目录',
          storage_local_base_url: '本地访问基地址',
          storage_s3_bucket: 'S3 Bucket',
          storage_s3_region: 'S3 Region',
          storage_s3_endpoint: 'S3 Endpoint',
          storage_s3_access_key_id: 'S3 Access Key ID',
          storage_s3_secret_access_key: 'S3 Secret Access Key',
          storage_s3_public_url: 'S3 公共访问 URL',
          storage_s3_object_prefix: 'S3 对象前缀',
          storage_s3_path_style: 'S3 Path Style',
          storage_r2_bucket: 'R2 Bucket',
          storage_r2_endpoint: 'R2 Endpoint',
          storage_r2_access_key_id: 'R2 Access Key ID',
          storage_r2_secret_access_key: 'R2 Secret Access Key',
          storage_r2_public_url: 'R2 公共访问 URL',
          storage_r2_object_prefix: 'R2 对象前缀',
          storage_oss_bucket: 'OSS Bucket',
          storage_oss_endpoint: 'OSS Endpoint',
          storage_oss_access_key_id: 'OSS Access Key ID',
          storage_oss_access_key_secret: 'OSS Access Key Secret',
          storage_oss_public_url: 'OSS 公共访问 URL',
          storage_oss_object_prefix: 'OSS 对象前缀',
          storage_imagebed_endpoint: '图床上传接口地址',
          storage_imagebed_method: '图床请求方法',
          storage_imagebed_file_field: '图床文件字段名',
          storage_imagebed_headers: '图床请求头',
          storage_imagebed_form_data: '图床额外表单参数',
          storage_imagebed_url_path: '图床响应 URL 路径',
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

export function resolveSettingsPage() {
  return UploadsSettingsPage
}
