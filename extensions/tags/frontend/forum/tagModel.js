import { ResourceModel } from '@bias/core'

export class TagModel extends ResourceModel {
  name() {
    return this.attribute('name')
  }

  slug() {
    return this.attribute('slug')
  }

  description() {
    return this.attribute('description')
  }

  color() {
    return this.attribute('color') || '#6c7a89'
  }

  icon() {
    return this.attribute('icon')
  }

  discussionCount() {
    return this.attribute('discussion_count') ?? this.attribute('discussionCount') ?? 0
  }

  parent() {
    return this.attribute('parent') || this.rawRelationship('parent')
  }

  children() {
    return this.attribute('children') || []
  }

  lastPostedDiscussion() {
    return this.attribute('last_posted_discussion') || this.attribute('lastPostedDiscussion') || null
  }
}
