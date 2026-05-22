import { createListItemRegistry } from './shared.js'


const approvalQueueNoteTemplates = createListItemRegistry()

export const registerAdminApprovalQueueNoteTemplate = approvalQueueNoteTemplates.register
export const getAdminApprovalQueueNoteTemplates = approvalQueueNoteTemplates.get
