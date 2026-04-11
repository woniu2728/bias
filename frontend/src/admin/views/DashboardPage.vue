<template>
  <AdminPage
    className="DashboardPage"
    icon="fas fa-chart-bar"
    title="仪表盘"
    description="查看论坛概况和系统状态"
  >
    <div class="DashboardPage-widgets">
      <!-- 状态小部件 -->
      <div class="Widget StatusWidget">
        <div class="Widget-header">
          <h3>系统状态</h3>
        </div>
        <div class="Widget-content">
          <div class="StatusWidget-items">
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">PHP版本</div>
              <div class="StatusWidget-value">{{ stats.phpVersion || '-' }}</div>
            </div>
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">数据库</div>
              <div class="StatusWidget-value">{{ stats.dbDriver || '-' }}</div>
            </div>
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">队列驱动</div>
              <div class="StatusWidget-value">{{ stats.queueDriver || '-' }}</div>
            </div>
            <div class="StatusWidget-item">
              <div class="StatusWidget-label">会话驱动</div>
              <div class="StatusWidget-value">{{ stats.sessionDriver || '-' }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 统计小部件 -->
      <div class="Widget StatsWidget">
        <div class="Widget-header">
          <h3>论坛统计</h3>
        </div>
        <div class="Widget-content">
          <div class="StatsWidget-items">
            <div class="StatsWidget-item">
              <div class="StatsWidget-icon">
                <i class="fas fa-users"></i>
              </div>
              <div class="StatsWidget-info">
                <div class="StatsWidget-value">{{ stats.totalUsers || 0 }}</div>
                <div class="StatsWidget-label">用户总数</div>
              </div>
            </div>
            <div class="StatsWidget-item">
              <div class="StatsWidget-icon">
                <i class="fas fa-comments"></i>
              </div>
              <div class="StatsWidget-info">
                <div class="StatsWidget-value">{{ stats.totalDiscussions || 0 }}</div>
                <div class="StatsWidget-label">讨论总数</div>
              </div>
            </div>
            <div class="StatsWidget-item">
              <div class="StatsWidget-icon">
                <i class="fas fa-comment"></i>
              </div>
              <div class="StatsWidget-info">
                <div class="StatsWidget-value">{{ stats.totalPosts || 0 }}</div>
                <div class="StatsWidget-label">帖子总数</div>
              </div>
            </div>
            <div class="StatsWidget-item">
              <div class="StatsWidget-icon StatsWidget-icon--warning">
                <i class="fas fa-flag"></i>
              </div>
              <div class="StatsWidget-info">
                <div class="StatsWidget-value">{{ stats.openFlags || 0 }}</div>
                <div class="StatsWidget-label">待处理举报</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 快速操作 -->
      <div class="Widget ActionsWidget">
        <div class="Widget-header">
          <h3>快速操作</h3>
        </div>
        <div class="Widget-content">
          <div class="ActionsWidget-items">
            <router-link to="/admin/basics" class="ActionsWidget-item">
              <i class="fas fa-pencil-alt"></i>
              <span>编辑基础设置</span>
            </router-link>
            <router-link to="/admin/permissions" class="ActionsWidget-item">
              <i class="fas fa-key"></i>
              <span>管理权限</span>
            </router-link>
            <router-link to="/admin/users" class="ActionsWidget-item">
              <i class="fas fa-users"></i>
              <span>管理用户</span>
            </router-link>
            <router-link to="/admin/flags" class="ActionsWidget-item">
              <i class="fas fa-flag"></i>
              <span>处理举报</span>
            </router-link>
            <router-link to="/admin/appearance" class="ActionsWidget-item">
              <i class="fas fa-paint-brush"></i>
              <span>自定义外观</span>
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import api from '../../api'

const stats = ref({
  phpVersion: null,
  dbDriver: null,
  queueDriver: null,
  sessionDriver: null,
  totalUsers: 0,
  totalDiscussions: 0,
  totalPosts: 0,
  openFlags: 0,
})

onMounted(async () => {
  try {
    const data = await api.get('/admin/stats')
    stats.value = data
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
})
</script>

<style scoped>
.DashboardPage-widgets {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.Widget {
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
}

.Widget-header {
  padding: 15px 20px;
  border-bottom: 1px solid #e3e8ed;
}

.Widget-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.Widget-content {
  padding: 20px;
}

/* 状态小部件 */
.StatusWidget-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.StatusWidget-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.StatusWidget-label {
  font-size: 13px;
  color: #999;
}

.StatusWidget-value {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

/* 统计小部件 */
.StatsWidget-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.StatsWidget-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: #f5f8fa;
  border-radius: 3px;
}

.StatsWidget-icon {
  width: 50px;
  height: 50px;
  background: #4d698e;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.StatsWidget-icon i {
  font-size: 20px;
  color: white;
}

.StatsWidget-icon--warning {
  background: #e67e22;
}

.StatsWidget-info {
  flex: 1;
}

.StatsWidget-value {
  font-size: 24px;
  font-weight: 700;
  color: #333;
  margin-bottom: 3px;
}

.StatsWidget-label {
  font-size: 13px;
  color: #666;
}

/* 快速操作 */
.ActionsWidget-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.ActionsWidget-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px;
  background: #f5f8fa;
  border-radius: 3px;
  color: #555;
  text-decoration: none;
  transition: all 0.2s;
}

.ActionsWidget-item:hover {
  background: #e8eef5;
  color: #4d698e;
  text-decoration: none;
}

.ActionsWidget-item i {
  font-size: 18px;
  width: 24px;
  text-align: center;
}
</style>
