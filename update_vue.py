import re
with open('admin/src/views/QuotesView.vue', 'r', encoding='utf-8') as f:
    content = f.read()

main_tabs_end = content.find('      </el-tabs>\n    </el-card>')

etf_template = """
        <!-- ETF数据标签页 -->
        <el-tab-pane label="ETF数据" name="etf-data">
          <el-tabs v-model="etfTab" @tab-change="handleETFTabChange">
            <!-- ETF实时行情 -->
            <el-tab-pane label="ETF实时行情" name="etf-stocks">
              <div class="tab-content">
                <div class="search-section">
                  <el-row :gutter="16" align="middle">
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-input
                        v-model="etfSearchKeyword"
                        placeholder="搜索ETF代码或名称"
                        clearable
                        @input="handleETFSearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                      </el-input>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="4" :lg="4" :xl="4">
                      <el-button @click="refreshETFData" :loading="etfLoading" :style="{ width: '100%' }">
                        <el-icon><Refresh /></el-icon>
                        刷新
                      </el-button>
                    </el-col>
                  </el-row>
                </div>

                <el-table
                  :data="etfData"
                  :loading="etfLoading"
                  stripe
                  :style="{ width: '100%' }"
                  class="responsive-table"
                >
                  <el-table-column prop="code" label="代码" width="80" show-overflow-tooltip />
                  <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
                  <el-table-column prop="current_price" label="现价" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getPriceClass(scope.row.current_price, scope.row.pre_close)">
                        {{ formatPrice(scope.row.current_price) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="change_percent" label="涨跌幅" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getChangeClass(scope.row.change_percent)">
                        {{ formatPercent(scope.row.change_percent) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="open" label="开盘" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPrice(scope.row.open) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="high" label="最高" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPrice(scope.row.high) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="low" label="最低" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPrice(scope.row.low) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="volume" label="成交量" min-width="90" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatVolume(scope.row.volume) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="amount" label="成交额" min-width="90" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatAmount(scope.row.amount) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="update_time" label="更新时间" min-width="120" show-overflow-tooltip />
                </el-table>

                <div class="pagination-section">
                  <el-pagination
                    v-model:current-page="etfCurrentPage"
                    v-model:page-size="etfPageSize"
                    :total="etfTotal"
                    :page-sizes="[20, 50, 100, 200]"
                    layout="total, sizes, prev, pager, next, jumper"
                    @size-change="handleETFPageSizeChange"
                    @current-change="handleETFPageChange"
                  />
                </div>
              </div>
            </el-tab-pane>

            <!-- ETF历史行情 -->
            <el-tab-pane label="ETF历史行情" name="etf-historical">
              <div class="tab-content">
                <div class="search-section">
                  <el-row :gutter="16" align="middle">
                    <el-col :xs="24" :sm="12" :md="6" :lg="6" :xl="6">
                      <el-input
                        v-model="etfHistoricalSearchKeyword"
                        placeholder="搜索ETF代码或名称"
                        clearable
                        @input="handleETFHistoricalSearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                      </el-input>
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="4" :lg="4" :xl="4">
                      <el-date-picker
                        v-model="etfHistoricalStartDate"
                        type="date"
                        placeholder="开始日期"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="handleETFHistoricalDateChange"
                        :style="{ width: '100%' }"
                      />
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="4" :lg="4" :xl="4">
                      <el-date-picker
                        v-model="etfHistoricalEndDate"
                        type="date"
                        placeholder="结束日期"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="handleETFHistoricalDateChange"
                        :style="{ width: '100%' }"
                      />
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="3" :lg="3" :xl="3">
                      <el-button @click="refreshETFHistoricalData" :loading="etfHistoricalLoading" :style="{ width: '100%' }">
                        <el-icon><Refresh /></el-icon>
                        刷新
                      </el-button>
                    </el-col>
                  </el-row>
                </div>

                <el-table
                  :data="etfHistoricalData"
                  :loading="etfHistoricalLoading"
                  stripe
                  :style="{ width: '100%' }"
                  class="responsive-table"
                >
                  <el-table-column prop="code" label="代码" width="80" show-overflow-tooltip fixed="left" />
                  <el-table-column prop="name" label="名称" width="120" show-overflow-tooltip fixed="left" />
                  <el-table-column prop="date" label="日期" width="100" show-overflow-tooltip />
                  <el-table-column prop="open" label="开盘" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPrice(scope.row.open) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="close" label="收盘" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPrice(scope.row.close) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="high" label="最高" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPrice(scope.row.high) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="low" label="最低" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPrice(scope.row.low) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="pre_close" label="昨收" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPrice(scope.row.pre_close) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="change_amount" label="涨跌额" min-width="88" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getChangeClass(scope.row.change)">
                        {{ formatPrice(scope.row.change) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="volume" label="成交量" min-width="90" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatVolume(scope.row.volume) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="amount" label="成交额" min-width="90" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatAmount(scope.row.amount) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="change_percent" label="涨跌幅" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getChangeClass(scope.row.change_percent)">
                        {{ formatPercent(scope.row.change_percent) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="turnover_rate" label="换手率" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPercent(scope.row.turnover_rate) }}
                    </template>
                  </el-table-column>
                </el-table>

                <div class="pagination-section">
                  <el-pagination
                    v-model:current-page="etfHistoricalCurrentPage"
                    v-model:page-size="etfHistoricalPageSize"
                    :total="etfHistoricalTotal"
                    :page-sizes="[20, 50, 100, 200]"
                    layout="total, sizes, prev, pager, next, jumper"
                    @size-change="handleETFHistoricalPageSizeChange"
                    @current-change="handleETFHistoricalPageChange"
                  />
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>
"""

content = content[:main_tabs_end] + etf_template + content[main_tabs_end:]

script_vars = """
// ETF数据
const etfTab = ref('etf-stocks')
const etfData = ref<any[]>([])
const etfLoading = ref(false)
const etfCurrentPage = ref(1)
const etfPageSize = ref(20)
const etfTotal = ref(0)
const etfSearchKeyword = ref('')

const etfHistoricalData = ref<any[]>([])
const etfHistoricalLoading = ref(false)
const etfHistoricalCurrentPage = ref(1)
const etfHistoricalPageSize = ref(20)
const etfHistoricalTotal = ref(0)
const etfHistoricalSearchKeyword = ref('')
const etfHistoricalStartDate = ref('')
const etfHistoricalEndDate = ref('')
"""

# Insert vars before hkhistorical end date roughly, or inside <script setup... just find loading = ref(false)
# Let's find "const hkIndexHistoricalEndDate = ref('')"
script_vars_idx = content.find("const hkIndexHistoricalEndDate = ref('')")
if script_vars_idx != -1:
    end_of_line = content.find('\n', script_vars_idx)
    content = content[:end_of_line+1] + script_vars + content[end_of_line+1:]

script_methods = """
// ********** ETF 行情方法 **********
const fetchETFData = async () => {
  etfLoading.value = true
  try {
    const response = await quotesService.getETFQuotes({
      page: etfCurrentPage.value,
      pageSize: etfPageSize.value,
      keyword: etfSearchKeyword.value
    })
    if (response.success) {
      etfData.value = response.data
      etfTotal.value = response.total
    }
  } catch (error) {
    ElMessage.error('获取ETF实时行情失败')
  } finally {
    etfLoading.value = false
  }
}

const handleETFSearch = () => {
  etfCurrentPage.value = 1
  fetchETFData()
}

const refreshETFData = () => {
  fetchETFData()
}

const handleETFPageChange = (val: number) => {
  etfCurrentPage.value = val
  fetchETFData()
}

const handleETFPageSizeChange = (val: number) => {
  etfPageSize.value = val
  etfCurrentPage.value = 1
  fetchETFData()
}

const fetchETFHistoricalData = async () => {
  etfHistoricalLoading.value = true
  try {
    const response = await quotesService.getETFHistoricalQuotes({
      page: etfHistoricalCurrentPage.value,
      pageSize: etfHistoricalPageSize.value,
      keyword: etfHistoricalSearchKeyword.value,
      startDate: etfHistoricalStartDate.value,
      endDate: etfHistoricalEndDate.value
    })
    if (response.success) {
      etfHistoricalData.value = response.data
      etfHistoricalTotal.value = response.total
    }
  } catch (error) {
    ElMessage.error('获取ETF历史行情失败')
  } finally {
    etfHistoricalLoading.value = false
  }
}

const handleETFHistoricalSearch = () => {
  etfHistoricalCurrentPage.value = 1
  fetchETFHistoricalData()
}

const handleETFHistoricalDateChange = () => {
  etfHistoricalCurrentPage.value = 1
  fetchETFHistoricalData()
}

const refreshETFHistoricalData = () => {
  fetchETFHistoricalData()
}

const handleETFHistoricalPageChange = (val: number) => {
  etfHistoricalCurrentPage.value = val
  fetchETFHistoricalData()
}

const handleETFHistoricalPageSizeChange = (val: number) => {
  etfHistoricalPageSize.value = val
  etfHistoricalCurrentPage.value = 1
  fetchETFHistoricalData()
}

const handleETFTabChange = (tab: any) => {
  if (tab === 'etf-stocks' && etfData.value.length === 0) {
    fetchETFData()
  } else if (tab === 'etf-historical' && etfHistoricalData.value.length === 0) {
    fetchETFHistoricalData()
  }
}

"""

script_methods_idx = content.find('const handleMainTabChange = (tab: any) => {')
if script_methods_idx != -1:
    content = content[:script_methods_idx] + script_methods + content[script_methods_idx:]

content = content.replace("else if (tab === 'hk-share') {", "else if (tab === 'hk-share') {\n    if (hkStockData.value.length === 0) fetchHKStockData()\n  } else if (tab === 'etf-data') {\n    if (etfData.value.length === 0) fetchETFData()\n  } else if (tab === 'never_used_dummy_to_keep_original_code') {")

refresh_call = '''    if (mainTab.value === 'etf-data') {
      if (etfTab.value === 'etf-stocks') fetchETFData()
      else if (etfTab.value === 'etf-historical') fetchETFHistoricalData()
    }'''
content = content.replace("if (mainTab.value === 'a-share') {", refresh_call + "\n    else if (mainTab.value === 'a-share') {")

with open('admin/src/views/QuotesView.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print("Python edit applied successfully!")
