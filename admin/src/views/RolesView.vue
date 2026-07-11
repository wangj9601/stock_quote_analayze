<template>
  <div class="roles-view">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>角色管理</span>
          <el-button type="primary" @click="openCreate">新建角色</el-button>
        </div>
      </template>
      <el-table :data="roles" v-loading="loading" stripe>
        <el-table-column prop="code" label="Code" width="140" />
        <el-table-column prop="name" label="名称" width="160" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column label="系统内置" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_system ? 'info' : 'success'">{{ row.is_system ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="goPermissions(row)">配置权限</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" :disabled="row.is_system" @click="removeRole(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑角色' : '新建角色'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="Code" v-if="!editing">
          <el-input v-model="form.code" placeholder="如 vip" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { rolesService, type FrontendRole } from '@/services/roles.service'

const router = useRouter()
const roles = ref<FrontendRole[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref<FrontendRole | null>(null)
const form = ref({ code: '', name: '', description: '' })

async function loadRoles() {
  loading.value = true
  try {
    roles.value = await rolesService.listRoles()
  } catch (e) {
    ElMessage.error('加载角色失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { code: '', name: '', description: '' }
  dialogVisible.value = true
}

function openEdit(row: FrontendRole) {
  editing.value = row
  form.value = { code: row.code, name: row.name, description: row.description || '' }
  dialogVisible.value = true
}

async function saveRole() {
  try {
    if (editing.value) {
      await rolesService.updateRole(editing.value.id, { name: form.value.name, description: form.value.description })
      ElMessage.success('更新成功')
    } else {
      await rolesService.createRole(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadRoles()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function removeRole(row: FrontendRole) {
  await ElMessageBox.confirm(`确定删除角色「${row.name}」？`, '提示', { type: 'warning' })
  await rolesService.deleteRole(row.id)
  ElMessage.success('已删除')
  await loadRoles()
}

function goPermissions(row: FrontendRole) {
  router.push(`/roles/${row.id}/permissions`)
}

onMounted(loadRoles)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
