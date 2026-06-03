import { ModelExtender, ResourceModel, StoreExtender } from './resourceModel.js'

export class ForumModel extends ResourceModel {
  apiEndpoint() {
    return '/'
  }
}

export class UserModel extends ResourceModel {
  username() {
    return attr(this, 'username')
  }

  slug() {
    return attr(this, 'slug')
  }

  displayName() {
    return attr(this, 'displayName', 'display_name') ?? this.username()
  }

  avatarUrl() {
    return attr(this, 'avatarUrl', 'avatar_url')
  }

  avatarSrcset() {
    return attr(this, 'avatarSrcset', 'avatar_srcset')
  }

  email() {
    return attr(this, 'email')
  }

  isEmailConfirmed() {
    return attr(this, 'isEmailConfirmed', 'is_email_confirmed')
  }

  preferences() {
    return attr(this, 'preferences') || {}
  }

  groups() {
    return hasMany(this, 'groups')
  }

  isAdmin() {
    return attr(this, 'isAdmin', 'is_admin')
  }

  joinTime() {
    return dateAttr(this, 'joinTime', 'join_time', 'created_at')
  }

  lastSeenAt() {
    return dateAttr(this, 'lastSeenAt', 'last_seen_at')
  }

  markedAllAsReadAt() {
    return dateAttr(this, 'markedAllAsReadAt', 'marked_all_as_read_at')
  }

  unreadNotificationCount() {
    return attr(this, 'unreadNotificationCount', 'unread_notification_count')
  }

  newNotificationCount() {
    return attr(this, 'newNotificationCount', 'new_notification_count')
  }

  discussionCount() {
    return attr(this, 'discussionCount', 'discussion_count')
  }

  commentCount() {
    return attr(this, 'commentCount', 'comment_count')
  }

  canEdit() {
    return attr(this, 'canEdit', 'can_edit')
  }

  canEditCredentials() {
    return attr(this, 'canEditCredentials', 'can_edit_credentials')
  }

  canEditGroups() {
    return attr(this, 'canEditGroups', 'can_edit_groups')
  }

  canDelete() {
    return attr(this, 'canDelete', 'can_delete')
  }

  isOnline() {
    const lastSeenAt = this.lastSeenAt()
    return lastSeenAt instanceof Date && Date.now() - lastSeenAt.getTime() < 5 * 60 * 1000
  }

  savePreferences(preferences = {}) {
    return this.save({
      preferences: {
        ...this.preferences(),
        ...(preferences || {}),
      },
    })
  }
}

export class GroupModel extends ResourceModel {
  static ADMINISTRATOR_ID = '1'
  static GUEST_ID = '2'
  static MEMBER_ID = '3'

  name() {
    return attr(this, 'name') ?? this.nameSingular()
  }

  nameSingular() {
    return attr(this, 'nameSingular', 'name_singular', 'name')
  }

  namePlural() {
    return attr(this, 'namePlural', 'name_plural', 'name')
  }

  color() {
    return attr(this, 'color')
  }

  icon() {
    return attr(this, 'icon')
  }

  isHidden() {
    return attr(this, 'isHidden', 'is_hidden')
  }

  position() {
    return attr(this, 'position')
  }
}

export class DiscussionModel extends ResourceModel {
  title() {
    return attr(this, 'title')
  }

  slug() {
    return attr(this, 'slug')
  }

  createdAt() {
    return dateAttr(this, 'createdAt', 'created_at')
  }

  user() {
    return hasOne(this, 'user')
  }

  firstPost() {
    return hasOne(this, 'firstPost', 'first_post')
  }

  lastPostedAt() {
    return dateAttr(this, 'lastPostedAt', 'last_posted_at')
  }

  lastPostedUser() {
    return hasOne(this, 'lastPostedUser', 'last_posted_user')
  }

  lastPost() {
    return hasOne(this, 'lastPost', 'last_post')
  }

  lastPostNumber() {
    return attr(this, 'lastPostNumber', 'last_post_number')
  }

  commentCount() {
    return attr(this, 'commentCount', 'comment_count') ?? 0
  }

  replyCount() {
    return Math.max(0, Number(this.commentCount() || 0) - 1)
  }

  posts() {
    return hasMany(this, 'posts')
  }

  mostRelevantPost() {
    return hasOne(this, 'mostRelevantPost', 'most_relevant_post')
  }

  lastReadAt() {
    return dateAttr(this, 'lastReadAt', 'last_read_at')
  }

  lastReadPostNumber() {
    return attr(this, 'lastReadPostNumber', 'last_read_post_number')
  }

  unreadCount() {
    return attr(this, 'unreadCount', 'unread_count') ?? 0
  }

  isUnread() {
    return Boolean(this.unreadCount())
  }

  isRead() {
    return !this.isUnread()
  }

  hiddenAt() {
    return dateAttr(this, 'hiddenAt', 'hidden_at')
  }

  hiddenUser() {
    return hasOne(this, 'hiddenUser', 'hidden_user')
  }

  isHidden() {
    return Boolean(this.hiddenAt())
  }

  canReply() {
    return attr(this, 'canReply', 'can_reply')
  }

  canRename() {
    return attr(this, 'canRename', 'can_rename')
  }

  canHide() {
    return attr(this, 'canHide', 'can_hide')
  }

  canDelete() {
    return attr(this, 'canDelete', 'can_delete')
  }

  postIds() {
    const relationship = this.rawRelationship('posts')
    return Array.isArray(relationship) ? relationship.map(item => item.id) : []
  }

  removePost(id) {
    const relationship = this.rawRelationship('posts')
    if (!Array.isArray(relationship)) return
    const index = relationship.findIndex(item => String(item.id) === String(id))
    if (index >= 0) relationship.splice(index, 1)
  }
}

export class PostModel extends ResourceModel {
  number() {
    return attr(this, 'number')
  }

  createdAt() {
    return dateAttr(this, 'createdAt', 'created_at')
  }

  contentType() {
    return attr(this, 'contentType', 'content_type', 'type')
  }

  content() {
    return attr(this, 'content')
  }

  contentHtml() {
    return attr(this, 'contentHtml', 'content_html')
  }

  contentPlain() {
    return stripHtml(this.contentHtml())
  }

  renderFailed() {
    return attr(this, 'renderFailed', 'render_failed')
  }

  discussion() {
    return hasOne(this, 'discussion')
  }

  user() {
    return hasOne(this, 'user')
  }

  ipAddress() {
    return attr(this, 'ipAddress', 'ip_address')
  }

  editedAt() {
    return dateAttr(this, 'editedAt', 'edited_at')
  }

  editedUser() {
    return hasOne(this, 'editedUser', 'edited_user')
  }

  isEdited() {
    return Boolean(this.editedAt())
  }

  hiddenAt() {
    return dateAttr(this, 'hiddenAt', 'hidden_at')
  }

  hiddenUser() {
    return hasOne(this, 'hiddenUser', 'hidden_user')
  }

  isHidden() {
    return Boolean(this.hiddenAt())
  }

  canEdit() {
    return attr(this, 'canEdit', 'can_edit')
  }

  canHide() {
    return attr(this, 'canHide', 'can_hide')
  }

  canDelete() {
    return attr(this, 'canDelete', 'can_delete')
  }
}

export class NotificationModel extends ResourceModel {
  contentType() {
    return attr(this, 'contentType', 'content_type', 'type')
  }

  content() {
    return attr(this, 'content')
  }

  createdAt() {
    return dateAttr(this, 'createdAt', 'created_at')
  }

  isRead() {
    return Boolean(attr(this, 'isRead', 'is_read'))
  }

  user() {
    return hasOne(this, 'user')
  }

  fromUser() {
    return hasOne(this, 'fromUser', 'from_user')
  }

  subject() {
    return hasOne(this, 'subject')
  }
}

export function registerDefaultResourceModels(store) {
  if (!store || typeof store.add !== 'function') {
    return store
  }
  new StoreExtender()
    .add('forum', ForumModel)
    .add('users', UserModel)
    .add('groups', GroupModel)
    .add('discussions', DiscussionModel)
    .add('posts', PostModel)
    .add('notifications', NotificationModel)
    .extend({ store })
  return store
}

export function extendDefaultResourceModels() {
  return [
    new ModelExtender(UserModel).hasMany('groups'),
    new ModelExtender(DiscussionModel).hasOne('user').hasOne('firstPost').hasOne('lastPost').hasMany('posts'),
    new ModelExtender(PostModel).hasOne('discussion').hasOne('user'),
    new ModelExtender(NotificationModel).hasOne('fromUser').hasOne('subject'),
  ]
}

function attr(model, ...names) {
  for (const name of names) {
    const value = model.attribute(name)
    if (value !== undefined) return value
  }
  return undefined
}

function dateAttr(model, ...names) {
  const value = attr(model, ...names)
  return ResourceModel.transformDate(value)
}

function hasOne(model, ...names) {
  for (const name of names) {
    if (model.rawRelationship(name) !== undefined) {
      return ResourceModel.hasOne(name).call(model)
    }
  }
  return false
}

function hasMany(model, ...names) {
  for (const name of names) {
    if (model.rawRelationship(name) !== undefined) {
      return ResourceModel.hasMany(name).call(model)
    }
  }
  return false
}

function stripHtml(value) {
  if (typeof value !== 'string') return value
  return value.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
}
