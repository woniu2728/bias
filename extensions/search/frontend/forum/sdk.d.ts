export declare function buildSearchTokens(query?: any): string[]
export declare function escapeHtml(value?: any): string
export declare function highlightSearchText(value?: any, query?: any, maxLength?: any): string
export declare function stripHtml(value?: any): string
export declare function truncateText(value?: any, maxLength?: any): string
export declare function resolveSearchMetaPayload(options?: Record<string, any>): Record<string, any>
export declare function useSearchFilterCatalog(target?: any): Record<string, any>
export declare function registerSearchFilter(item?: Record<string, any>): Record<string, any>
export declare function getRegisteredSearchFilters(target?: any): Record<string, any>[]
export declare function ensureSearchFilterCatalogLoaded(target?: any): Promise<any>
export declare function buildSearchFilterQuery(baseQuery?: any, syntax?: any): string
export declare function buildSearchFilterSuggestions(target?: any): Record<string, any>[]
export declare function getSearchSources(context?: Record<string, any>): any[]
export declare function registerSearchSource(definition?: Record<string, any>): any
export declare function getSearchModalProvider(context?: Record<string, any>): any
export declare function registerSearchModalProvider(definition?: Record<string, any>): any
export declare function getSearchModalSections(context?: Record<string, any>): any[]
export declare function getSearchModalSection(context?: Record<string, any>): any
export declare function registerSearchModalSection(definition?: Record<string, any>): any
