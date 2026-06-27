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
