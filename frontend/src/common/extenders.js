import { ModelExtender, StoreExtender } from './resourceModel.js'
import {
  AdminExtender,
  ExportsExtender,
  ForumExtender,
  NotificationExtender,
  RoutesExtender,
  SearchExtender,
  ThemeModeExtender,
  extendAdmin,
  extendForum,
} from './frontendExtenders.js'

export {
  ModelExtender,
  StoreExtender,
  NotificationExtender,
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
  StoreExtender as Store,
  NotificationExtender as Notification,
  RoutesExtender as Routes,
  SearchExtender as Search,
  ThemeModeExtender as ThemeMode,
  ExportsExtender as Exports,
}

export default {
  Model: ModelExtender,
  Store: StoreExtender,
  Notification: NotificationExtender,
  Routes: RoutesExtender,
  Search: SearchExtender,
  ThemeMode: ThemeModeExtender,
  AdminExtender,
  Exports: ExportsExtender,
  ForumExtender,
  extendAdmin,
  extendForum,
}
