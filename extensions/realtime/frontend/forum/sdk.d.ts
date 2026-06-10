export declare function useForumRealtimeStore(...args: any[]): any
export declare const FORUM_REALTIME_REFRESH_EVENT_TYPES: Set<string>
export declare function getForumRealtimeEventPolicy(eventType?: any, context?: Record<string, any>): Record<string, boolean>
export declare function getTrackedDiscussionIdsFromDiscussionItems(items?: any[]): number[]
export declare function getTrackedDiscussionIdsFromPostItems(items?: any[]): number[]
export declare function hasTrackedDiscussionId(targetIds?: any[], discussionId?: any): boolean
export declare function mergeForumEventPayload(resourceStore?: any, event?: any): void
export declare function shouldAppendForumRealtimePost(eventType?: any, context?: Record<string, any>): boolean
export declare function shouldMarkForumEventAsNewReply(eventType?: any, context?: Record<string, any>): boolean
export declare function shouldRefreshForumEvent(eventType?: any, context?: Record<string, any>): boolean
export declare function shouldUpsertForumRealtimePost(eventType?: any, context?: Record<string, any>): boolean
export declare function getForumRealtimeEvents(context?: Record<string, any>): any[]
export declare function registerForumRealtimeEvent(definition?: Record<string, any>): any
