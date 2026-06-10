import {
  api,
} from '@bias/core'
import { extendForum } from '@bias/forum'

export const extend = [
  extendForum('uploads', registerUploadsForum),
]

function registerUploadsForum(forum) {
  forum
    .composerTool({
      key: 'upload',
      moduleId: 'uploads',
      title: '上传附件',
      icon: 'fas fa-file-upload',
      order: 10,
      run: ({ openAttachmentPicker }) => {
        openAttachmentPicker?.()
      },
    })
    .composerTool({
      key: 'image',
      moduleId: 'uploads',
      title: '图片',
      icon: 'fas fa-image',
      order: 100,
      run: ({ openImagePicker }) => {
        openImagePicker?.()
      },
    })
    .composerUploadHandler({
      key: 'uploads-default',
      moduleId: 'uploads',
      order: 10,
      async upload({ file, asImage }) {
        const uploaded = await uploadComposerFile(file)
        return {
          ...uploaded,
          markdown: buildUploadedFileMarkdown(uploaded.original_name || file?.name, uploaded.url, {
            image: asImage,
          }),
        }
      },
    })

  for (const definition of uploadsCopyDefinitions()) {
    forum.uiCopy({
      moduleId: 'uploads',
      ...definition,
    })
  }
}

function uploadsCopyDefinitions() {
  return [
    textCopy('composer-notice-upload-label', 646, '上传'),
    {
      key: 'composer-upload-progress',
      order: 646,
      surfaces: ['composer-upload-progress'],
      resolve: ({ asImage, fileName }) => ({
        text: `正在上传${asImage ? '图片' : '附件'}：${fileName || ''}`,
      }),
    },
    {
      key: 'composer-upload-inserted',
      order: 646,
      surfaces: ['composer-upload-inserted'],
      resolve: ({ asImage }) => ({
        text: `${asImage ? '图片' : '附件'}已插入编辑器`,
      }),
    },
    {
      key: 'composer-upload-failed',
      order: 646,
      surfaces: ['composer-upload-failed'],
      resolve: ({ asImage }) => ({
        text: asImage ? '图片上传失败' : '附件上传失败',
      }),
    },
    {
      key: 'composer-upload-unavailable',
      order: 646,
      surfaces: ['composer-upload-unavailable'],
      resolve: () => ({
        text: '上传功能未启用',
      }),
    },
  ]
}

async function uploadComposerFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  return api.post('/uploads', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

function buildUploadedFileMarkdown(fileName, url, options = {}) {
  const { image = false } = options
  const fallback = image ? '图片' : '附件'
  const safeLabel = sanitizeMarkdownLabel(stripFileExtension(fileName), fallback)
  return image ? `![${safeLabel}](${url})` : `[${safeLabel}](${url})`
}

function sanitizeMarkdownLabel(value, fallback) {
  const sanitized = String(value || '')
    .replace(/[[\]\r\n]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  return sanitized || fallback
}

function stripFileExtension(fileName) {
  return String(fileName || '').replace(/\.[^.]+$/, '')
}

function textCopy(key, order, text) {
  return {
    key,
    order,
    surfaces: [key],
    resolve: () => ({ text }),
  }
}
