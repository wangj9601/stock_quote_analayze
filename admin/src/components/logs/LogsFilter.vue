<template>
  <div class="logs-filter">
    <el-card>
      <template #header>
        <div class="filter-header">
          <span>筛选条件</span>
          <el-button type="primary" size="small" @click="applyFilters">
            应用筛选
          </el-button>
        </div>
      </template>

      <el-form :model="localFilters" label-width="80px">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
            <el-form-item label="日志级别">
              <el-select v-model="localFilters.level" placeholder="选择日志级别" class="w-full">
                <el-option v-if="mode === 'app'" label="警告+错误" value="WARNING,ERROR" />
                <el-option label="全部" value="all" />
                <el-option label="信息" value="INFO" />
                <el-option label="警告" value="WARNING" />
                <el-option label="错误" value="ERROR" />
                <el-option label="调试" value="DEBUG" />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
            <el-form-item label="开始日期">
              <el-date-picker
                v-model="localFilters.startDate"
                type="date"
                placeholder="选择开始日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                class="w-full"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
            <el-form-item label="结束日期">
              <el-date-picker
                v-model="localFilters.endDate"
                type="date"
                placeholder="选择结束日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                class="w-full"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
            <el-form-item label="关键词">
              <el-input
                v-model="localFilters.keyword"
                placeholder="输入关键词搜索"
                clearable
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row v-if="mode === 'app'" :gutter="16">
          <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
            <el-form-item label="来源文件">
              <el-select
                v-model="localFilters.sourceFile"
                placeholder="全部白名单文件"
                clearable
                class="w-full"
              >
                <el-option
                  v-for="f in sourceFiles"
                  :key="f.name"
                  :label="f.name"
                  :value="f.name"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row>
          <el-col :span="24">
            <div class="filter-actions">
              <el-button @click="clearFilters">清空筛选</el-button>
              <el-button type="primary" @click="applyFilters">应用筛选</el-button>
            </div>
          </el-col>
        </el-row>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import dayjs from 'dayjs'
import type { AppLogFileInfo, LogFilter } from '@/types/logs.types'

interface Props {
  filters: LogFilter
  mode?: 'db' | 'app'
  sourceFiles?: AppLogFileInfo[]
}

interface Emits {
  (e: 'update-filters', filters: Partial<LogFilter>): void
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'db',
  sourceFiles: () => [],
})
const emit = defineEmits<Emits>()

const localFilters = reactive<LogFilter>({
  type: 'all',
  level: 'all',
  startDate: null,
  endDate: null,
  collect_source: null,
  keyword: '',
  sourceFile: null,
})

watch(() => props.filters, (newFilters) => {
  Object.assign(localFilters, newFilters)
}, { deep: true, immediate: true })

const applyFilters = () => {
  emit('update-filters', { ...localFilters })
}

const clearFilters = () => {
  if (props.mode === 'app') {
    Object.assign(localFilters, {
      type: 'app',
      level: 'WARNING,ERROR',
      startDate: dayjs().subtract(1, 'day').format('YYYY-MM-DD'),
      endDate: dayjs().format('YYYY-MM-DD'),
      collect_source: null,
      keyword: '',
      sourceFile: null,
    })
  } else {
    Object.assign(localFilters, {
      type: 'all',
      level: 'all',
      startDate: null,
      endDate: null,
      collect_source: null,
      keyword: '',
      sourceFile: null,
    })
  }
  applyFilters()
}
</script>

<style scoped>
.logs-filter {
  @apply mb-6;
}

.filter-header {
  @apply flex justify-between items-center;
}

.filter-actions {
  @apply flex justify-end space-x-2 mt-4;
}

.w-full {
  width: 100%;
}

@media (max-width: 768px) {
  .logs-filter {
    @apply mb-4;
  }

  .filter-header {
    @apply flex-col items-start space-y-2;
  }

  .filter-actions {
    @apply flex-col space-y-2 mt-4;
  }

  .filter-actions .el-button {
    width: 100%;
  }
}
</style>
