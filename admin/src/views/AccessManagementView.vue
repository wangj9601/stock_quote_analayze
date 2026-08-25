<template>
  <div class="access-management-view">
    <el-tabs v-model="activeTab" type="border-card" @tab-change="onTabChange">
      <el-tab-pane label="用户管理" name="users">
        <UsersView />
      </el-tab-pane>
      <el-tab-pane label="角色管理" name="roles">
        <RolesView />
      </el-tab-pane>
      <el-tab-pane label="权限资源" name="permissions">
        <PermissionsView />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import UsersView from './UsersView.vue'
import RolesView from './RolesView.vue'
import PermissionsView from './PermissionsView.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref<'users' | 'roles' | 'permissions'>('users')

function onTabChange(name: string | number) {
  const tab = typeof name === 'number' ? String(name) : name
  router.replace({ path: '/access-management', query: { ...route.query, tab } }).catch(() => {})
}

watch(
  () => route.query.tab,
  (tab) => {
    if (tab === 'users' || tab === 'roles' || tab === 'permissions') {
      activeTab.value = tab
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.access-management-view {
  padding: 0;
}
.access-management-view :deep(.el-tabs__content) {
  padding: 16px 0 0;
}
</style>
