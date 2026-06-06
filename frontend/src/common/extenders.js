import { ModelExtender, StoreExtender } from './resourceModel.js'
import {
  AdminExtender,
  AdminDashboardExtender,
  AdminPageExtender,
  ExportsExtender,
  ForumExtender,
  NotificationExtender,
  PostTypesExtender,
  RoutesExtender,
  SearchExtender,
  ThemeModeExtender,
} from './frontendExtenders.js'

export {
  ModelExtender,
  StoreExtender,
  NotificationExtender,
  PostTypesExtender,
  RoutesExtender,
  SearchExtender,
  ThemeModeExtender,
  AdminExtender,
  AdminDashboardExtender,
  AdminPageExtender,
  ExportsExtender,
  ForumExtender,
}

export {
  ModelExtender as Model,
  StoreExtender as Store,
  NotificationExtender as Notification,
  PostTypesExtender as PostTypes,
  RoutesExtender as Routes,
  SearchExtender as Search,
  ThemeModeExtender as ThemeMode,
  AdminExtender as Admin,
  AdminDashboardExtender as AdminDashboard,
  AdminPageExtender as AdminPage,
  ExportsExtender as Exports,
  ForumExtender as Forum,
}

export default {
  Model: ModelExtender,
  Store: StoreExtender,
  Notification: NotificationExtender,
  PostTypes: PostTypesExtender,
  Routes: RoutesExtender,
  Search: SearchExtender,
  ThemeMode: ThemeModeExtender,
  Admin: AdminExtender,
  AdminDashboard: AdminDashboardExtender,
  AdminPage: AdminPageExtender,
  Exports: ExportsExtender,
  Forum: ForumExtender,
}
