export declare function createAdminExtensionApp(options?: Record<string, any>): any
export declare function getAdminExtensionInitializers(): any[]
export declare function resetAdminExtensionAppRuntime(): void
export declare function bootstrapEnabledAdminExtensions(options?: Record<string, any>): Promise<{ addedRouteCount: number }>
export declare function getAdminInitializers(): any[]
export declare function resetLoadedAdminExtensions(): void
export declare function resetLoadedAdminExtensionsWhenRuntimeChanges(...args: any[]): any
export declare const adminRuntimeRegistry: any
export declare function createAdminRuntimeRegistry(...args: any[]): any
export declare class AdminExtender {
  constructor(context?: string | null)
}
export declare class ExportsExtender {
  constructor(exports?: Record<string, any>)
}
export declare const Exports: typeof ExportsExtender
export declare function extendAdmin(callback: (admin: AdminExtender) => AdminExtender | void): AdminExtender
export declare function extendAdmin(context: string, callback?: (admin: AdminExtender) => AdminExtender | void): AdminExtender
export declare function registerAdminPermissionScope(definition: Record<string, any>): any
export declare function getAdminPermissionScopes(context?: Record<string, any>): any[]
