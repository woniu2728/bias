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
        uploadPolicyTitle: '上传策略',
        uploadPolicyDescription: '限制核心站点资源上传大小；头像和附件上传策略由对应扩展管理。',
        uploadSiteAssetMaxSizeLabel: '站点资源最大体积（MB）',
        uploadSizeHelpText: 'Logo/Favicon 默认 2MB。',
      }),
    })
    .pageConfig(ADVANCED_PAGE_KEY, {
      key: 'uploads-advanced-config',
      moduleId: 'uploads',
      order: 30,
      resolve: () => ({
        enableUploadPolicySection: true,
        defaultSettings: {
          upload_site_asset_max_size_mb: 2,
        },
        sensitiveLabels: {
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
