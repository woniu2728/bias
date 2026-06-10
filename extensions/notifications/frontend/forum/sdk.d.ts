export declare function getNotificationRenderers(context?: Record<string, any>): any[]
export declare function registerNotificationRenderer(definition?: Record<string, any>): any
export declare function registerNotificationType(type?: string, component?: any, options?: Record<string, any>): any
export declare function getNotificationComponent(type?: string): any
export declare function getNotificationNavigationTarget(type?: string, notification?: any): any
export declare function getResolvedNotificationTypes(): any[]
export declare function getNotificationTypeDefinition(type?: string): any
export declare function getNotificationIcon(type?: string): string
export declare function getNotificationIconClass(type?: string): string
export declare function getNotificationText(notification?: any, fallbackMessage?: string): string
export declare function getNotificationTextHtml(notification?: any, fallbackMessage?: string): string
export declare function getNotificationPresentation(notification?: any, fallbackMessage?: string): Record<string, any>
export declare function getNotificationPresentationModel(notification?: any, fallbackMessage?: string): Record<string, any>
export declare function resolveNotificationGroup(notification?: any, fallbackTitle?: string): Record<string, any>
export declare function useNotificationGroups(notificationItems?: any[], fallbackTitle?: string): any
