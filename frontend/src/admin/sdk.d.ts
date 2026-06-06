export * from '../common/sdk'

export declare function createAdminExtensionApp(options?: Record<string, any>): any
export declare function bootstrapEnabledAdminExtensions(options?: Record<string, any>): Promise<{ addedRouteCount: number }>
export declare const adminRuntimeRegistry: any
