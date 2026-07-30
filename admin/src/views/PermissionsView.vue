<template>
  <div class="permissions-view">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>权限资源浏览</span>
          <el-button type="primary" :loading="syncing" @click="syncRegistry">从注册表同步</el-button>
        </div>
      </template>
      <div class="tree-scroll">
        <el-tree
          :data="tree"
          node-key="code"
          default-expand-all
          :props="{ label: renderLabel, children: 'children' }"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { permissionsService, type PermissionTreeNode } from '@/services/roles.service'

const tree = ref<PermissionTreeNode[]>([])
const syncing = ref(false)

function renderLabel(data: PermissionTreeNode) {
  return `${data.name} (${data.code})`
}

async function loadTree() {
  const resp = await permissionsService.getTree()
  tree.value = resp.tree
}

async function syncRegistry() {
  syncing.value = true
  try {
    const result = await permissionsService.sync()
    ElMessage.success(`同步完成：新增 ${result.created}，更新 ${result.updated}`)
    await loadTree()
  } catch (e) {
    ElMessage.error('同步失败')
  } finally {
    syncing.value = false
  }
}

onMounted(async () => {
  try {
    await loadTree()
  } catch {
    ElMessage.error('加载权限树失败，请确认后端已重启并注册 /api/admin/permissions 路由')
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.tree-scroll {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
</style>
