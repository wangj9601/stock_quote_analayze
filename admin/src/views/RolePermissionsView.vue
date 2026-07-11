<template>
  <div class="role-permissions-view">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>角色权限配置：{{ roleName }}</span>
          <div>
            <el-button @click="$router.push('/roles')">返回</el-button>
            <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          </div>
        </div>
      </template>
      <p class="hint">每个频道/标签/按钮独立勾选，不联动父子节点。</p>
      <el-tree
        ref="treeRef"
        :data="tree"
        node-key="code"
        show-checkbox
        check-strictly
        default-expand-all
        :props="{ label: 'name', children: 'children' }"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { rolesService, permissionsService, type PermissionTreeNode } from '@/services/roles.service'

const route = useRoute()
const roleId = Number(route.params.id)
const roleName = ref('')
const tree = ref<PermissionTreeNode[]>([])
const loading = ref(false)
const saving = ref(false)
const treeRef = ref()

async function load() {
  loading.value = true
  try {
    const roles = await rolesService.listRoles()
    roleName.value = roles.find(r => r.id === roleId)?.name || String(roleId)
    const treeResp = await permissionsService.getTree()
    tree.value = treeResp.tree
    const permResp = await rolesService.getRolePermissions(roleId)
    treeRef.value?.setCheckedKeys(permResp.permission_codes || [])
    await nextTick()
    treeRef.value?.setCheckedKeys(permResp.permission_codes || [])
  } catch (e) {
    ElMessage.error('加载权限树失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const codes = treeRef.value?.getCheckedKeys(false) as string[] || []
    await rolesService.setRolePermissions(roleId, codes)
    ElMessage.success('权限已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.hint {
  color: #666;
  margin-bottom: 12px;
  font-size: 13px;
}
</style>
