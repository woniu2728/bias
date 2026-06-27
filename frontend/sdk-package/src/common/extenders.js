import { ResourceNormalizerExtender } from './resourceNormalizers.js'
import { ModelExtender, StoreExtender } from './resourceModel.js'
import {
  AdminExtender,
  ExportsExtender,
  ForumExtender,
  NotificationExtender,
  PostTypesExtender,
  RoutesExtender,
  SearchExtender,
  ThemeModeExtender,
  extendAdmin,
  extendForum,
} from './frontendExtenders.js'

export {
  ModelExtender,
  ModelExtender as ResourceModelExtender,
  ResourceNormalizerExtender,
  StoreExtender,
  NotificationExtender,
  PostTypesExtender,
  RoutesExtender,
  SearchExtender,
  ThemeModeExtender,
  AdminExtender,
  ExportsExtender,
  ForumExtender,
  extendAdmin,
  extendForum,
}

export {
  ModelExtender as Model,
  ResourceNormalizerExtender as ResourceNormalizer,
  StoreExtender as Store,
  NotificationExtender as Notification,
  PostTypesExtender as PostTypes,
  RoutesExtender as Routes,
  SearchExtender as Search,
  ThemeModeExtender as ThemeMode,
  ExportsExtender as Exports,
}

export default {
  Model: ModelExtender,
  ResourceModelExtender: ModelExtender,
  ResourceNormalizer: ResourceNormalizerExtender,
  Store: StoreExtender,
  Notification: NotificationExtender,
  PostTypes: PostTypesExtender,
  Routes: RoutesExtender,
  Search: SearchExtender,
  ThemeMode: ThemeModeExtender,
  AdminExtender,
  Exports: ExportsExtender,
  ForumExtender,
  extendAdmin,
  extendForum,
}
