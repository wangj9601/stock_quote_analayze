<template>
  <div class="indicators-view">
    <el-card class="query-section">
      <el-tabs v-model="activeMainTab" @tab-change="handleMainTabChange">
        <!-- 指标数据查询 -->
        <el-tab-pane label="指标数据查询" name="query">
          <div class="tab-header">
            <div class="header-actions">
              <el-button @click="refreshData" :loading="loading">
                <el-icon><Refresh /></el-icon>
                刷新数据
              </el-button>
            </div>
          </div>
          <el-tabs v-model="activeIndicator" @tab-change="handleTabChange">
        <!-- MA 移动平均线 -->
        <el-tab-pane label="MA (移动平均线)" name="ma">
          <div class="tab-content">
            <div class="filter-section">
              <el-row :gutter="16" align="middle">
                <el-col :span="6">
                  <el-input v-model="filters.code" placeholder="股票代码" clearable @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-select v-model="filters.market_type" placeholder="市场类型" clearable @change="handleFilterChange">
                    <el-option label="A股 (CN)" value="CN" />
                    <el-option label="港股 (HK)" value="HK" />
                  </el-select>
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.start_date" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.end_date" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
              </el-row>
            </div>

            <el-table :data="tableData" v-loading="loading" stripe style="width: 100%">
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column prop="date" label="日期" width="120" />
              <el-table-column prop="ma5" label="MA5">
                <template #default="scope">{{ scope.row.ma5?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="ma10" label="MA10">
                <template #default="scope">{{ scope.row.ma10?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="ma20" label="MA20">
                <template #default="scope">{{ scope.row.ma20?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="ma30" label="MA30">
                <template #default="scope">{{ scope.row.ma30?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="ma60" label="MA60">
                <template #default="scope">{{ scope.row.ma60?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="ma120" label="MA120">
                <template #default="scope">{{ scope.row.ma120?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="ma200" label="MA200">
                <template #default="scope">{{ scope.row.ma200?.toFixed(2) || '-' }}</template>
              </el-table-column>
            </el-table>

            <div class="pagination-section">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :total="total"
                :page-sizes="[20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handlePageChange"
                @size-change="handleSizeChange"
              />
            </div>
          </div>
        </el-tab-pane>

        <!-- MACD 指标 -->
        <el-tab-pane label="MACD" name="macd">
          <div class="tab-content">
            <div class="filter-section">
              <el-row :gutter="16" align="middle">
                <el-col :span="6">
                  <el-input v-model="filters.code" placeholder="股票代码" clearable @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-select v-model="filters.market_type" placeholder="市场类型" clearable @change="handleFilterChange">
                    <el-option label="A股 (CN)" value="CN" />
                    <el-option label="港股 (HK)" value="HK" />
                  </el-select>
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.start_date" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.end_date" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
              </el-row>
            </div>

            <el-table :data="tableData" v-loading="loading" stripe style="width: 100%">
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column prop="date" label="日期" width="120" />
              <el-table-column prop="dif" label="DIF (快线)">
                <template #default="scope">{{ scope.row.dif?.toFixed(3) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="dea" label="DEA (慢线)">
                <template #default="scope">{{ scope.row.dea?.toFixed(3) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="macd" label="MACD (柱状图)">
                <template #default="scope">
                  <span :style="{ color: scope.row.macd > 0 ? '#f56c6c' : '#67c23a' }">
                    {{ scope.row.macd?.toFixed(3) || '-' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="ema12" label="EMA12">
                <template #default="scope">{{ scope.row.ema12?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="ema26" label="EMA26">
                <template #default="scope">{{ scope.row.ema26?.toFixed(2) || '-' }}</template>
              </el-table-column>
            </el-table>

            <div class="pagination-section">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :total="total"
                :page-sizes="[20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handlePageChange"
                @size-change="handleSizeChange"
              />
            </div>
          </div>
        </el-tab-pane>

        <!-- RSI 指标 -->
        <el-tab-pane label="RSI" name="rsi">
          <div class="tab-content">
            <div class="filter-section">
              <el-row :gutter="16" align="middle">
                <el-col :span="6">
                  <el-input v-model="filters.code" placeholder="股票代码" clearable @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-select v-model="filters.market_type" placeholder="市场类型" clearable @change="handleFilterChange">
                    <el-option label="A股 (CN)" value="CN" />
                    <el-option label="港股 (HK)" value="HK" />
                  </el-select>
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.start_date" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.end_date" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
              </el-row>
            </div>

            <el-table :data="tableData" v-loading="loading" stripe style="width: 100%">
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column prop="date" label="日期" width="120" />
              <el-table-column prop="rsi6" label="RSI6">
                <template #default="scope">{{ scope.row.rsi6?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="rsi12" label="RSI12">
                <template #default="scope">{{ scope.row.rsi12?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="rsi24" label="RSI24">
                <template #default="scope">{{ scope.row.rsi24?.toFixed(2) || '-' }}</template>
              </el-table-column>
            </el-table>

            <div class="pagination-section">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :total="total"
                :page-sizes="[20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handlePageChange"
                @size-change="handleSizeChange"
              />
            </div>
          </div>
        </el-tab-pane>

        <!-- KDJ 指标 -->
        <el-tab-pane label="KDJ" name="kdj">
          <div class="tab-content">
            <div class="filter-section">
              <el-row :gutter="16" align="middle">
                <el-col :span="6">
                  <el-input v-model="filters.code" placeholder="股票代码" clearable @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-select v-model="filters.market_type" placeholder="市场类型" clearable @change="handleFilterChange">
                    <el-option label="A股 (CN)" value="CN" />
                    <el-option label="港股 (HK)" value="HK" />
                  </el-select>
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.start_date" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.end_date" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
              </el-row>
            </div>

            <el-table :data="tableData" v-loading="loading" stripe style="width: 100%">
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column prop="date" label="日期" width="120" />
              <el-table-column prop="k" label="K">
                <template #default="scope">{{ scope.row.k?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="d" label="D">
                <template #default="scope">{{ scope.row.d?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="j" label="J">
                <template #default="scope">{{ scope.row.j?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="rsv" label="RSV">
                <template #default="scope">{{ scope.row.rsv?.toFixed(2) || '-' }}</template>
              </el-table-column>
            </el-table>

            <div class="pagination-section">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :total="total"
                :page-sizes="[20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handlePageChange"
                @size-change="handleSizeChange"
              />
            </div>
          </div>
        </el-tab-pane>

        <!-- BOLL 布林带 -->
        <el-tab-pane label="BOLL" name="boll">
          <div class="tab-content">
            <div class="filter-section">
              <el-row :gutter="16" align="middle">
                <el-col :span="6">
                  <el-input v-model="filters.code" placeholder="股票代码" clearable @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-select v-model="filters.market_type" placeholder="市场类型" clearable @change="handleFilterChange">
                    <el-option label="A股 (CN)" value="CN" />
                    <el-option label="港股 (HK)" value="HK" />
                  </el-select>
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.start_date" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.end_date" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
              </el-row>
            </div>

            <el-table :data="tableData" v-loading="loading" stripe style="width: 100%">
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column prop="date" label="日期" width="120" />
              <el-table-column prop="mid" label="MID (中轨)">
                <template #default="scope">{{ scope.row.mid?.toFixed(3) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="upper" label="UPPER (上轨)">
                <template #default="scope">{{ scope.row.upper?.toFixed(3) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="lower" label="LOWER (下轨)">
                <template #default="scope">{{ scope.row.lower?.toFixed(3) || '-' }}</template>
              </el-table-column>
            </el-table>

            <div class="pagination-section">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :total="total"
                :page-sizes="[20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handlePageChange"
                @size-change="handleSizeChange"
              />
            </div>
          </div>
        </el-tab-pane>

        <!-- MAVOL 成交量移动平均线 -->
        <el-tab-pane label="MAVOL" name="mavol">
          <div class="tab-content">
            <div class="filter-section">
              <el-row :gutter="16" align="middle">
                <el-col :span="6">
                  <el-input v-model="filters.code" placeholder="股票代码" clearable @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-select v-model="filters.market_type" placeholder="市场类型" clearable @change="handleFilterChange">
                    <el-option label="A股 (CN)" value="CN" />
                    <el-option label="港股 (HK)" value="HK" />
                  </el-select>
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.start_date" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.end_date" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
              </el-row>
            </div>

            <el-table :data="tableData" v-loading="loading" stripe style="width: 100%">
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column prop="date" label="日期" width="120" />
              <el-table-column prop="mavol5" label="MAVOL5">
                <template #default="scope">{{ scope.row.mavol5?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="mavol10" label="MAVOL10">
                <template #default="scope">{{ scope.row.mavol10?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="mavol20" label="MAVOL20">
                <template #default="scope">{{ scope.row.mavol20?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="mavol30" label="MAVOL30">
                <template #default="scope">{{ scope.row.mavol30?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="mavol60" label="MAVOL60">
                <template #default="scope">{{ scope.row.mavol60?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="mavol120" label="MAVOL120">
                <template #default="scope">{{ scope.row.mavol120?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="mavol200" label="MAVOL200">
                <template #default="scope">{{ scope.row.mavol200?.toFixed(2) || '-' }}</template>
              </el-table-column>
            </el-table>

            <div class="pagination-section">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :total="total"
                :page-sizes="[20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handlePageChange"
                @size-change="handleSizeChange"
              />
            </div>
          </div>
        </el-tab-pane>

        <!-- PVFRS 均值频率共振策略 -->
        <el-tab-pane label="PVFRS (均值频率共振)" name="pvfrs">
          <div class="tab-content">
            <div class="filter-section">
              <el-row :gutter="16" align="middle">
                <el-col :span="6">
                  <el-input v-model="filters.code" placeholder="股票代码" clearable @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-select v-model="filters.market_type" placeholder="市场类型" clearable @change="handleFilterChange">
                    <el-option label="A股 (CN)" value="CN" />
                    <el-option label="港股 (HK)" value="HK" />
                  </el-select>
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.start_date" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="filters.end_date" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" @change="handleFilterChange" />
                </el-col>
              </el-row>
            </div>

            <el-table :data="tableData" v-loading="loading" stripe style="width: 100%">
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column prop="date" label="日期" width="120" />
              <el-table-column prop="macro_displacement_delta" label="宏观位移Δ" width="120">
                <template #default="scope">
                  <span :style="{ color: scope.row.macro_displacement_delta > 0 ? '#f56c6c' : '#67c23a' }">
                    {{ scope.row.macro_displacement_delta?.toFixed(3) || '-' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="instant_deviation" label="即时偏离度" width="120">
                <template #default="scope">
                  <span :style="{ color: scope.row.instant_deviation > 0 ? '#f56c6c' : '#67c23a' }">
                    {{ scope.row.instant_deviation?.toFixed(3) || '-' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="bias" label="乖离率(Bias)" width="120">
                <template #default="scope">
                  <span :style="{ color: scope.row.bias > 0 ? '#f56c6c' : '#67c23a' }">
                    {{ scope.row.bias ? (scope.row.bias * 100).toFixed(2) + '%' : '-' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="rising_days_z" label="上涨天数Z" width="110">
                <template #default="scope">{{ scope.row.rising_days_z || '-' }}</template>
              </el-table-column>
              <el-table-column prop="falling_days_f" label="下跌天数F" width="110">
                <template #default="scope">{{ scope.row.falling_days_f || '-' }}</template>
              </el-table-column>
              <el-table-column prop="efficiency_m20_minus_m" label="进出效率" width="120">
                <template #default="scope">
                  <span :style="{ color: scope.row.efficiency_m20_minus_m > 0 ? '#f56c6c' : '#67c23a' }">
                    {{ scope.row.efficiency_m20_minus_m?.toFixed(2) || '-' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="ma20_d" label="MA20">
                <template #default="scope">{{ scope.row.ma20_d?.toFixed(2) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="mavol20_m" label="MAVOL20">
                <template #default="scope">{{ scope.row.mavol20_m?.toFixed(2) || '-' }}</template>
              </el-table-column>
            </el-table>

            <div class="pagination-section">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :total="total"
                :page-sizes="[20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handlePageChange"
                @size-change="handleSizeChange"
              />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
        </el-tab-pane>

        <!-- 指标数据生成 -->
        <el-tab-pane label="指标数据生成" name="generate">
          <div class="tab-content">
            <div class="generation-section">
              <el-row :gutter="16" class="mb-4">
                <el-col :span="8">
                  <el-input v-model="generationForm.code" placeholder="请输入股票代码" clearable>
                    <template #prepend>股票代码</template>
                  </el-input>
                </el-col>
                <el-col :span="8">
                  <el-select v-model="generationForm.market_type" placeholder="选择市场类型" style="width: 100%">
                    <el-option label="A股 (CN)" value="CN" />
                    <el-option label="港股 (HK)" value="HK" />
                  </el-select>
                </el-col>
                <el-col :span="8">
                  <el-button type="primary" @click="generateIndicators" :loading="generating" :disabled="!canGenerate">
                    <el-icon><Setting /></el-icon>
                    生成指标数据
                  </el-button>
                </el-col>
              </el-row>

              <el-divider content-position="left">选择要生成的指标</el-divider>
              
              <div class="mb-3">
                <el-checkbox 
                  v-model="isAllIndicatorsSelected" 
                  :indeterminate="isIndeterminate"
                  @change="handleSelectAllIndicators"
                >
                  全选
                </el-checkbox>
              </div>
              
              <el-row :gutter="16">
                <el-col :span="24">
                  <el-checkbox-group v-model="generationForm.indicators">
                    <el-row :gutter="16">
                      <el-col :span="6">
                        <el-checkbox label="ma" border>MA (移动平均线)</el-checkbox>
                      </el-col>
                      <el-col :span="6">
                        <el-checkbox label="mavol" border>MAVOL (成交量移动平均)</el-checkbox>
                      </el-col>
                      <el-col :span="6">
                        <el-checkbox label="macd" border>MACD</el-checkbox>
                      </el-col>
                      <el-col :span="6">
                        <el-checkbox label="kdj" border>KDJ</el-checkbox>
                      </el-col>
                      <el-col :span="6">
                        <el-checkbox label="rsi" border>RSI</el-checkbox>
                      </el-col>
                      <el-col :span="6">
                        <el-checkbox label="boll" border>BOLL (布林带)</el-checkbox>
                      </el-col>
                      <el-col :span="6">
                        <el-checkbox label="pvfrs" border>PVFRS</el-checkbox>
                      </el-col>
                    </el-row>
                  </el-checkbox-group>
                </el-col>
              </el-row>

              <el-divider content-position="left">生成结果</el-divider>
              
              <div v-if="generationResult" class="result-section">
                <el-alert
                  :title="generationResult.success ? '生成成功' : '生成失败'"
                  :type="generationResult.success ? 'success' : 'error'"
                  :description="generationResult.message"
                  show-icon
                  :closable="false"
                />
                
                <div v-if="generationResult.details" class="mt-4">
                  <el-descriptions title="生成详情" border>
                    <el-descriptions-item 
                      v-for="(value, key) in generationResult.details" 
                      :key="key"
                      :label="getIndicatorLabel(key)"
                    >
                      <el-tag :type="value.success ? 'success' : 'danger'">
                        {{ value.success ? '成功' : '失败' }}: {{ value.message || value.count || '-' }}
                      </el-tag>
                    </el-descriptions-item>
                  </el-descriptions>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { Refresh, Search, Setting } from '@element-plus/icons-vue'
import { apiService } from '@/services/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const generating = ref(false)
const activeMainTab = ref('query')
const activeIndicator = ref('ma')
const tableData = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const generationResult = ref(null)

const filters = reactive({
  code: '',
  market_type: '',
  start_date: '',
  end_date: ''
})

const generationForm = reactive({
  code: '',
  market_type: '',
  indicators: []
})

const canGenerate = computed(() => {
  return generationForm.code && 
         generationForm.market_type && 
         generationForm.indicators.length > 0 &&
         !generating.value
})

// 全选相关计算属性
const allIndicatorTypes = ['ma', 'mavol', 'macd', 'kdj', 'rsi', 'boll', 'pvfrs']

const isAllIndicatorsSelected = computed(() => {
  return generationForm.indicators.length === allIndicatorTypes.length
})

const isIndeterminate = computed(() => {
  const selectedCount = generationForm.indicators.length
  if (selectedCount === 0) {
    return false
  } else if (selectedCount === allIndicatorTypes.length) {
    return false
  } else {
    return true
  }
})

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      ...filters
    }
    const response: any = await apiService.get(`/indicators/${activeIndicator.value}`, { params })
    if (response.success) {
      // 确保 data 始终是数组
      const data = response.data
      tableData.value = Array.isArray(data) ? data : (Array.isArray(data?.data) ? data.data : [])
      total.value = response.total || (Array.isArray(data) ? data.length : (data?.total || 0))
    } else {
      ElMessage.error('获取数据失败')
      tableData.value = []
      total.value = 0
    }
  } catch (error) {
    console.error('Fetch indicators error:', error)
    ElMessage.error('网络请求失败')
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const handleTabChange = () => {
  currentPage.value = 1
  fetchData()
}

const handleFilterChange = () => {
  currentPage.value = 1
  fetchData()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  fetchData()
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  fetchData()
}

const refreshData = () => {
  if (activeMainTab.value === 'query') {
    fetchData()
  }
}

const handleMainTabChange = () => {
  generationResult.value = null
}

const handleSelectAllIndicators = (checked: boolean) => {
  if (checked) {
    generationForm.indicators = [...allIndicatorTypes]
  } else {
    generationForm.indicators = []
  }
}

const getIndicatorLabel = (key: string) => {
  const labels = {
    ma: 'MA (移动平均线)',
    mavol: 'MAVOL (成交量移动平均)',
    macd: 'MACD',
    kdj: 'KDJ',
    rsi: 'RSI',
    boll: 'BOLL (布林带)',
    pvfrs: 'PVFRS'
  }
  return labels[key] || key
}

const generateIndicators = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要为股票 ${generationForm.code}(${generationForm.market_type === 'CN' ? 'A股' : '港股'}) 生成选中的指标数据吗？`,
      '确认生成',
      {
        confirmButtonText: '确定生成',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  generating.value = true
  generationResult.value = null
  
  try {
    const response: any = await apiService.post('/indicators/generate', {
      code: generationForm.code,
      market_type: generationForm.market_type,
      indicators: generationForm.indicators
    })
    
    if (response.success) {
      generationResult.value = {
        success: true,
        message: `成功为股票 ${generationForm.code} 生成指标数据`,
        details: response.data
      }
      ElMessage.success('指标数据生成成功')
    } else {
      generationResult.value = {
        success: false,
        message: response.message || '生成失败'
      }
      ElMessage.error('指标数据生成失败')
    }
  } catch (error) {
    console.error('Generate indicators error:', error)
    generationResult.value = {
      success: false,
      message: '网络请求失败'
    }
    ElMessage.error('网络请求失败')
  } finally {
    generating.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped lang="postcss">
.indicators-view {
  @apply space-y-6;
}

.page-header {
  @apply flex justify-between items-center mb-4;
}

.page-header h1 {
  @apply text-2xl font-bold text-gray-900;
}

.query-section {
  @apply shadow-sm rounded-lg;
}

.tab-content {
  @apply p-4;
}

.tab-header {
  @apply flex justify-end mb-4 p-4;
}

.filter-section {
  @apply mb-6 p-4 bg-gray-50 rounded-lg;
}

.pagination-section {
  @apply mt-6 flex justify-end;
}

.generation-section {
  @apply p-4;
}

.result-section {
  @apply mt-4;
}

:deep(.el-tabs__header) {
  @apply px-4 pt-4;
}

:deep(.el-checkbox-group .el-checkbox) {
  @apply mb-3;
}
</style>
