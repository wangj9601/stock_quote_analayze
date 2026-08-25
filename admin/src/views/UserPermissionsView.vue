<template>
  <div class="user-permissions-view">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <div>
            <div class="title">用户权限：{{ username }}</div>
            <div class="subtitle">
              角色「{{ detail?.role?.name }}」默认 {{ detail?.role_permission_codes?.length || 0 }} 项；
              当前生效 {{ detail?.effective_permission_codes?.length || 0 }} 项
              <el-tag v-if="detail?.override_count" size="small" type="warning" style="margin-left:8px">
                个性化 {{ detail?.override_count }} 项
              </el-tag>
            </div>
          </div>
          <div>
            <el-button @click="$router.push({ path: '/access-management', query: { tab: 'users' } })">返回</el-button>
            <el-button :disabled="!detail?.override_count" @click="resetToRole">恢复角色默认</el-button>
            <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          </div>
        </div>
      </template>
      <p class="hint">
        勾选为用户<strong>最终生效</strong>的权限。同一角色下，不同用户可单独配置（例如 A 可见选股、B 不可见）。
        与角色默认一致时不会写入个性化覆盖。
      </p>
      <el-tree
        ref="treeRef"
        :data="tree"
        node-key="code"
        show-checkbox
        check-strictly
        default-expand-all
        :props="{ label: renderLabel, children: 'children' }"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { permissionsService, type PermissionTreeNode } from '@/services/roles.service'
import { usersService, type UserPermissionsDetail } from '@/services/users.service'

const route = useRoute()
const userId = Number(route.params.id)
const username = ref(String(route.query.username || userId))
const tree = ref<PermissionTreeNode[]>([])
const detail = ref<UserPermissionsDetail | null>(null)
const loading = ref(false)
const saving = ref(false)
const treeRef = ref()

function renderLabel(data: PermissionTreeNode) {
  const inRole = detail.value?.role_permission_codes?.includes(data.code)
  return `${data.name}${inRole ? '' : ' (角色无)'}`
}

async function load() {
  loading.value = true
  try {
    const [treeResp, permResp] = await Promise.all([
      permissionsService.getTree(),
      usersService.getUserPermissions(userId)
    ])
    tree.value = treeResp.tree
    detail.value = permResp
    await nextTick()
    treeRef.value?.setCheckedKeys(permResp.effective_permission_codes || [])
  } catch (e) {
    ElMessage.error('加载用户权限失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const codes = treeRef.value?.getCheckedKeys(false) as string[] || []
    const result = await usersService.setUserPermissions(userId, codes)
    ElMessage.success(`已保存，个性化覆盖 ${result.override_count} 项`)
    await load()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function resetToRole() {
  await ElMessageBox.confirm('确定恢复为角色默认权限？将清除该用户所有个性化设置。', '提示', { type: 'warning' })
  await usersService.resetUserPermissions(userId)
  ElMessage.success('已恢复角色默认权限')
  await load()
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.title { font-weight: 600; font-size: 16px; }
.subtitle { font-size: 13px; color: #666; margin-top: 4px; }
.hint {
  color: #666;
  margin-bottom: 12px;
  font-size: 13px;
  line-height: 1.6;
}
</style>
