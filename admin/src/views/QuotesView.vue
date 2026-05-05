<template>
  <div class="quotes-view">
    <div class="page-header">
      <h1>行情数据</h1>
      <div class="header-actions">
        <el-button @click="refreshAllData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
    </div>

    <!-- 主标签组：A股 / 港股 -->
    <el-card class="tabs-section">
      <el-tabs v-model="mainTab" @tab-change="handleMainTabChange">
        <!-- A股数据标签页 -->
        <el-tab-pane label="A股数据" name="a-share">
          <el-tabs v-model="aShareTab" @tab-change="handleAShareTabChange">
            <!-- A股股票实时行情 -->
            <el-tab-pane label="股票实时行情" name="stocks">
              <div class="tab-content">
                <!-- 搜索和筛选 -->
                <div class="search-section">
                  <el-row :gutter="16" align="middle">
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-input
                        v-model="stockSearchKeyword"
                        placeholder="搜索股票代码或名称"
                        clearable
                        @input="handleStockSearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                      </el-input>
                    </el-col>
                    <el-col :xs="12" :sm="12" :md="4" :lg="4" :xl="4">
                      <el-select
                        v-model="stockMarketFilter"
                        placeholder="市场类型"
                        clearable
                        @change="handleStockMarketFilter"
                        :style="{ width: '100%' }"
                      >
                        <el-option label="全部" value="" />
                        <el-option label="上海" value="sh" />
                        <el-option label="深圳" value="sz" />
                        <el-option label="创业板" value="cy" />
                        <el-option label="北交所" value="bj" />
                      </el-select>
                    </el-col>
                    <el-col :xs="12" :sm="12" :md="4" :lg="4" :xl="4">
                      <el-select
                        v-model="stockSortBy"
                        placeholder="排序方式"
                        @change="handleStockSortChange"
                        :style="{ width: '100%' }"
                      >
                        <el-option label="涨跌幅（高到低）" value="change_percent" />
                        <el-option label="现价（高到低）" value="current_price" />
                        <el-option label="成交量（高到低）" value="volume" />
                        <el-option label="成交额（高到低）" value="amount" />
                        <el-option label="换手率（高到低）" value="turnover_rate" />
                        <el-option label="更新时间（倒序）" value="update_time" />
                      </el-select>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="4" :lg="4" :xl="4">
                      <el-button @click="refreshStockData" :loading="stockLoading" :style="{ width: '100%' }">
                        <el-icon><Refresh /></el-icon>
                        刷新
                      </el-button>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-button type="primary" plain @click="openTurnoverImportDialog" :style="{ width: '100%' }">
                        换手率导入
                      </el-button>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-button type="danger" plain @click="openDeleteRealtimeDialog" :style="{ width: '100%' }">
                        删除实时行情
                      </el-button>
                    </el-col>
                  </el-row>
                </div>

                <el-table
                  :data="stockData"
                  :loading="stockLoading"
                  stripe
                  :style="{ width: '100%' }"
                  class="responsive-table"
                >
                  <el-table-column prop="code" label="代码" width="80" show-overflow-tooltip />
                  <el-table-column prop="name" label="名称" min-width="100" show-overflow-tooltip />
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
                  <el-table-column prop="turnover_rate" label="换手率" min-width="90" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPercent(scope.row.turnover_rate) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="amount" label="成交额" min-width="90" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatAmount(scope.row.amount) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="update_time" label="更新时间" min-width="120" show-overflow-tooltip />
                  <el-table-column label="操作" width="100" fixed="right" align="center">
                    <template #default="scope">
                      <el-button type="danger" link @click="confirmDeleteStockRow(scope.row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- 分页组件 -->
                <div class="pagination-section">
                  <el-pagination
                    v-model:current-page="stockCurrentPage"
                    v-model:page-size="stockPageSize"
                    :total="stockTotal"
                    :page-sizes="[20, 50, 100, 200]"
                    layout="total, sizes, prev, pager, next, jumper"
                    @size-change="handleStockPageSizeChange"
                    @current-change="handleStockPageChange"
                  />
                </div>
              </div>
            </el-tab-pane>

            <!-- A股指数实时行情 -->
            <el-tab-pane label="指数实时行情" name="indices">
              <div class="tab-content">
                <div class="search-section">
                  <el-row :gutter="16" align="middle">
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-input
                        v-model="indexSearchKeyword"
                        placeholder="搜索指数代码或名称"
                        clearable
                        @input="handleIndexSearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                      </el-input>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="4" :lg="4" :xl="4">
                      <el-button @click="refreshIndexData" :loading="indexLoading" :style="{ width: '100%' }">
                        <el-icon><Refresh /></el-icon>
                        刷新
                      </el-button>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-button type="danger" plain @click="openDeleteIndexRealtimeDialog" :style="{ width: '100%' }">
                        删除指数实时行情
                      </el-button>
                    </el-col>
                  </el-row>
                </div>

                <el-table
                  :data="indexData"
                  :loading="indexLoading"
                  stripe
                  :style="{ width: '100%' }"
                  class="responsive-table"
                >
                  <el-table-column prop="code" label="代码" width="80" show-overflow-tooltip />
                  <el-table-column prop="name" label="名称" min-width="100" show-overflow-tooltip />
                  <el-table-column prop="price" label="点位" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getPriceClass(scope.row.price, scope.row.pre_close)">
                        {{ formatPrice(scope.row.price) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="pct_chg" label="涨跌幅" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getChangeClass(scope.row.pct_chg)">
                        {{ formatPercent(scope.row.pct_chg) }}
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
                  <el-table-column prop="update_time" label="更新时间" width="140" />
                  <el-table-column label="操作" width="100" fixed="right" align="center">
                    <template #default="scope">
                      <el-button type="danger" link @click="confirmDeleteIndexRow(scope.row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <div class="pagination-section">
                  <el-pagination
                    v-model:current-page="indexCurrentPage"
                    v-model:page-size="indexPageSize"
                    :total="indexTotal"
                    :page-sizes="[20, 50, 100]"
                    layout="total, sizes, prev, pager, next, jumper"
                    @size-change="handleIndexPageSizeChange"
                    @current-change="handleIndexPageChange"
                  />
                </div>
              </div>
            </el-tab-pane>

            <!-- A股历史行情数据 -->
            <el-tab-pane label="历史行情数据" name="historical">
              <div class="tab-content">
                <div class="search-section">
                  <el-row :gutter="16" align="middle">
                    <el-col :xs="24" :sm="12" :md="6" :lg="6" :xl="6">
                      <el-input
                        v-model="historicalSearchKeyword"
                        placeholder="搜索股票代码或名称"
                        clearable
                        @input="handleHistoricalSearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                      </el-input>
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="4" :lg="4" :xl="4">
                      <el-select v-model="historicalPeriod" placeholder="周期" :style="{ width: '100%' }" @change="handleHistoricalPeriodChange">
                        <el-option label="日线" value="daily" />
                        <el-option label="周线" value="weekly" />
                        <el-option label="月线" value="monthly" />
                        <el-option label="季线" value="quarterly" />
                        <el-option label="半年线" value="semiannual" />
                        <el-option label="年线" value="annual" />
                      </el-select>
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="4" :lg="4" :xl="4">
                      <el-date-picker
                        v-model="historicalStartDate"
                        type="date"
                        placeholder="开始日期"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="handleHistoricalDateChange"
                        :style="{ width: '100%' }"
                      />
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="4" :lg="4" :xl="4">
                      <el-date-picker
                        v-model="historicalEndDate"
                        type="date"
                        placeholder="结束日期"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="handleHistoricalDateChange"
                        :style="{ width: '100%' }"
                      />
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="3" :lg="3" :xl="3">
                      <el-button @click="refreshHistoricalData" :loading="historicalLoading" :style="{ width: '100%' }">
                        <el-icon><Refresh /></el-icon>
                        刷新
                      </el-button>
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="3" :lg="3" :xl="3">
                      <el-button type="success" plain @click="openExportDialog" :style="{ width: '100%' }">
                        <el-icon><Download /></el-icon>
                        导出
                      </el-button>
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="3" :lg="3" :xl="3">
                      <el-button type="primary" plain @click="openHistoricalTurnoverImportDialog" :style="{ width: '100%' }">
                        换手率更新
                      </el-button>
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="3" :lg="3" :xl="3">
                      <el-button type="danger" plain @click="openDeleteHistoricalDialog" :style="{ width: '100%' }">
                        删除历史行情
                      </el-button>
                    </el-col>
                  </el-row>
                </div>

                <el-table
                  :data="historicalData"
                  :loading="historicalLoading"
                  stripe
                  :style="{ width: '100%' }"
                  class="responsive-table"
                >
                  <el-table-column prop="code" label="代码" width="80" show-overflow-tooltip fixed="left" />
                  <el-table-column prop="name" label="名称" width="100" show-overflow-tooltip fixed="left" />
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
                  <el-table-column prop="volume" label="成交量" min-width="90" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatVolume(scope.row.volume) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="turnover_rate" label="换手率" min-width="90" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPercent(scope.row.turnover_rate) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="change_percent" label="涨跌幅" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getChangeClass(scope.row.change_percent)">
                        {{ formatPercent(scope.row.change_percent) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="100" fixed="right" align="center">
                    <template #default="scope">
                      <el-button type="danger" link @click="confirmDeleteHistoricalRow(scope.row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <div class="pagination-section">
                  <el-pagination
                    v-model:current-page="historicalCurrentPage"
                    v-model:page-size="historicalPageSize"
                    :total="historicalTotal"
                    :page-sizes="[20, 50, 100, 200]"
                    layout="total, sizes, prev, pager, next, jumper"
                    @size-change="handleHistoricalPageSizeChange"
                    @current-change="handleHistoricalPageChange"
                  />
                </div>
              </div>
            </el-tab-pane>

            <!-- A股行业板块实时行情 -->
            <el-tab-pane label="行业板块实时行情" name="industries">
              <div class="tab-content">
                <div class="search-section">
                  <el-row :gutter="16" align="middle">
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-input
                        v-model="industrySearchKeyword"
                        placeholder="搜索行业名称"
                        clearable
                        @input="handleIndustrySearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                      </el-input>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="4" :lg="4" :xl="4">
                      <el-button @click="refreshIndustryData" :loading="industryLoading" :style="{ width: '100%' }">
                        <el-icon><Refresh /></el-icon>
                        刷新
                      </el-button>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-button type="danger" plain @click="openDeleteIndustryRealtimeDialog" :style="{ width: '100%' }">
                        删除行业板块行情
                      </el-button>
                    </el-col>
                  </el-row>
                </div>

                <el-table
                  :data="industryData"
                  :loading="industryLoading"
                  stripe
                  :style="{ width: '100%' }"
                  class="responsive-table"
                >
                  <el-table-column prop="board_code" label="板块代码" width="100" show-overflow-tooltip />
                  <el-table-column prop="board_name" label="行业名称" min-width="120" show-overflow-tooltip />
                  <el-table-column prop="latest_price" label="点位" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatPrice(scope.row.latest_price) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="change_percent" label="涨跌幅" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getChangeClass(scope.row.change_percent)">
                        {{ formatPercent(scope.row.change_percent) }}
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
                  <el-table-column prop="leading_stock_name" label="领涨股" min-width="90" show-overflow-tooltip />
                  <el-table-column prop="update_time" label="更新时间" min-width="120" show-overflow-tooltip />
                  <el-table-column label="操作" width="100" fixed="right" align="center">
                    <template #default="scope">
                      <el-button type="danger" link @click="confirmDeleteIndustryRow(scope.row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <div class="pagination-section">
                  <el-pagination
                    v-model:current-page="industryCurrentPage"
                    v-model:page-size="industryPageSize"
                    :total="industryTotal"
                    :page-sizes="[20, 50, 100]"
                    layout="total, sizes, prev, pager, next, jumper"
                    @size-change="handleIndustryPageSizeChange"
                    @current-change="handleIndustryPageChange"
                  />
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <!-- 港股数据标签页 -->
        <el-tab-pane label="港股数据" name="hk-share">
          <el-tabs v-model="hkShareTab" @tab-change="handleHKShareTabChange">
            <!-- 港股实时行情 -->
            <el-tab-pane label="港股实时行情" name="hk-stocks">
              <div class="tab-content">
                <div class="search-section">
                  <el-row :gutter="16" align="middle">
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-input
                        v-model="hkStockSearchKeyword"
                        placeholder="搜索港股代码或名称"
                        clearable
                        @input="handleHKStockSearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                      </el-input>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="4" :lg="4" :xl="4">
                      <el-button @click="refreshHKStockData" :loading="hkStockLoading" :style="{ width: '100%' }">
                        <el-icon><Refresh /></el-icon>
                        刷新
                      </el-button>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-button type="danger" plain @click="openHkStockRtDeleteDialog" :style="{ width: '100%' }">
                        删除实时行情
                      </el-button>
                    </el-col>
                  </el-row>
                </div>

                <el-table
                  :data="hkStockData"
                  :loading="hkStockLoading"
                  stripe
                  :style="{ width: '100%' }"
                  class="responsive-table"
                >
                  <el-table-column prop="code" label="代码" width="80" show-overflow-tooltip />
                  <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
                  <el-table-column prop="trade_date" label="交易日" width="110" show-overflow-tooltip />
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
                  <el-table-column prop="update_time" label="更新时间" min-width="120" show-overflow-tooltip />
                  <el-table-column label="操作" width="88" fixed="right" align="center">
                    <template #default="scope">
                      <el-button type="danger" link @click="confirmDeleteHKStockRealtimeRow(scope.row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <div class="pagination-section">
                  <el-pagination
                    v-model:current-page="hkStockCurrentPage"
                    v-model:page-size="hkStockPageSize"
                    :total="hkStockTotal"
                    :page-sizes="[20, 50, 100, 200]"
                    layout="total, sizes, prev, pager, next, jumper"
                    @size-change="handleHKStockPageSizeChange"
                    @current-change="handleHKStockPageChange"
                  />
                </div>
              </div>
            </el-tab-pane>

            <!-- 港股历史行情 -->
            <el-tab-pane label="港股历史行情" name="hk-historical">
              <div class="tab-content">
                <div class="search-section">
                  <el-row :gutter="16" align="middle">
                    <el-col :xs="24" :sm="12" :md="6" :lg="6" :xl="6">
                      <el-input
                        v-model="hkHistoricalSearchKeyword"
                        placeholder="搜索港股代码或名称"
                        clearable
                        @input="handleHKHistoricalSearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                      </el-input>
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="4" :lg="4" :xl="4">
                      <el-date-picker
                        v-model="hkHistoricalStartDate"
                        type="date"
                        placeholder="开始日期"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="handleHKHistoricalDateChange"
                        :style="{ width: '100%' }"
                      />
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="4" :lg="4" :xl="4">
                      <el-date-picker
                        v-model="hkHistoricalEndDate"
                        type="date"
                        placeholder="结束日期"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="handleHKHistoricalDateChange"
                        :style="{ width: '100%' }"
                      />
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="3" :lg="3" :xl="3">
                      <el-button @click="refreshHKHistoricalData" :loading="hkHistoricalLoading" :style="{ width: '100%' }">
                        <el-icon><Refresh /></el-icon>
                        刷新
                      </el-button>
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="3" :lg="3" :xl="3">
                      <el-button type="success" plain @click="openHKExportDialog" :style="{ width: '100%' }">
                        <el-icon><Download /></el-icon>
                        导出
                      </el-button>
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="3" :lg="3" :xl="3">
                      <el-button type="danger" plain @click="openHkStockHistDeleteDialog" :style="{ width: '100%' }">
                        删除历史行情
                      </el-button>
                    </el-col>
                  </el-row>
                </div>

                <el-table
                  :data="hkHistoricalData"
                  :loading="hkHistoricalLoading"
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
                      <span :class="getChangeClass(scope.row.change_amount)">
                        {{ formatPrice(scope.row.change_amount) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="volume" label="成交量" min-width="90" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatVolume(scope.row.volume) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="change_percent" label="涨跌幅" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getChangeClass(scope.row.change_percent)">
                        {{ formatPercent(scope.row.change_percent) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="88" fixed="right" align="center">
                    <template #default="scope">
                      <el-button type="danger" link @click="confirmDeleteHKHistoricalStockRow(scope.row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <div class="pagination-section">
                  <el-pagination
                    v-model:current-page="hkHistoricalCurrentPage"
                    v-model:page-size="hkHistoricalPageSize"
                    :total="hkHistoricalTotal"
                    :page-sizes="[20, 50, 100, 200]"
                    layout="total, sizes, prev, pager, next, jumper"
                    @size-change="handleHKHistoricalPageSizeChange"
                    @current-change="handleHKHistoricalPageChange"
                  />
                </div>
              </div>
            </el-tab-pane>

            <!-- 港股指数实时行情 -->
            <el-tab-pane label="港股指数实时行情" name="hk-indices">
              <div class="tab-content">
                <div class="search-section">
                  <el-row :gutter="16" align="middle">
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-input
                        v-model="hkIndexSearchKeyword"
                        placeholder="搜索指数代码或名称"
                        clearable
                        @input="handleHKIndexSearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                      </el-input>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="4" :lg="4" :xl="4">
                      <el-button @click="refreshHKIndexData" :loading="hkIndexLoading" :style="{ width: '100%' }">
                        <el-icon><Refresh /></el-icon>
                        刷新
                      </el-button>
                    </el-col>
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-button type="danger" plain @click="openHkIdxRtDeleteDialog" :style="{ width: '100%' }">
                        删除指数实时行情
                      </el-button>
                    </el-col>
                  </el-row>
                </div>

                <el-table
                  :data="hkIndexData"
                  :loading="hkIndexLoading"
                  stripe
                  :style="{ width: '100%' }"
                  class="responsive-table"
                >
                  <el-table-column prop="code" label="代码" width="100" show-overflow-tooltip />
                  <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
                  <el-table-column prop="trade_date" label="交易日" width="110" show-overflow-tooltip />
                  <el-table-column prop="price" label="点位" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getPriceClass(scope.row.price, scope.row.pre_close)">
                        {{ formatPrice(scope.row.price) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="pct_chg" label="涨跌幅" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getChangeClass(scope.row.pct_chg)">
                        {{ formatPercent(scope.row.pct_chg) }}
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
                  <el-table-column prop="update_time" label="更新时间" width="140" />
                  <el-table-column label="操作" width="88" fixed="right" align="center">
                    <template #default="scope">
                      <el-button type="danger" link @click="confirmDeleteHKIndexRealtimeRow(scope.row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <div class="pagination-section">
                  <el-pagination
                    v-model:current-page="hkIndexCurrentPage"
                    v-model:page-size="hkIndexPageSize"
                    :total="hkIndexTotal"
                    :page-sizes="[20, 50, 100]"
                    layout="total, sizes, prev, pager, next, jumper"
                    @size-change="handleHKIndexPageSizeChange"
                    @current-change="handleHKIndexPageChange"
                  />
                </div>
              </div>
            </el-tab-pane>

            <!-- 港股指数历史行情 -->
            <el-tab-pane label="港股指数历史行情" name="hk-index-historical">
              <div class="tab-content">
                <div class="search-section">
                  <el-row :gutter="16" align="middle">
                    <el-col :xs="24" :sm="12" :md="6" :lg="6" :xl="6">
                      <el-input
                        v-model="hkIndexHistoricalSearchKeyword"
                        placeholder="搜索指数代码或名称"
                        clearable
                        @input="handleHKIndexHistoricalSearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                      </el-input>
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="4" :lg="4" :xl="4">
                      <el-date-picker
                        v-model="hkIndexHistoricalStartDate"
                        type="date"
                        placeholder="开始日期"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="handleHKIndexHistoricalDateChange"
                        :style="{ width: '100%' }"
                      />
                    </el-col>
                    <el-col :xs="12" :sm="6" :md="4" :lg="4" :xl="4">
                      <el-date-picker
                        v-model="hkIndexHistoricalEndDate"
                        type="date"
                        placeholder="结束日期"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="handleHKIndexHistoricalDateChange"
                        :style="{ width: '100%' }"
                      />
                    </el-col>
                    <el-col :xs="24" :sm="12" :md="4" :lg="4" :xl="4">
                      <el-button @click="refreshHKIndexHistoricalData" :loading="hkIndexHistoricalLoading" :style="{ width: '100%' }">
                        <el-icon><Refresh /></el-icon>
                        刷新
                      </el-button>
                    </el-col>
                    <el-col :xs="24" :sm="12" :md="5" :lg="5" :xl="5">
                      <el-button type="danger" plain @click="openHkIdxHistDeleteDialog" :style="{ width: '100%' }">
                        删除指数历史行情
                      </el-button>
                    </el-col>
                  </el-row>
                </div>

                <el-table
                  :data="hkIndexHistoricalData"
                  :loading="hkIndexHistoricalLoading"
                  stripe
                  :style="{ width: '100%' }"
                  class="responsive-table"
                >
                  <el-table-column prop="code" label="代码" width="100" show-overflow-tooltip fixed="left" />
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
                  <el-table-column prop="volume" label="成交量" min-width="90" show-overflow-tooltip>
                    <template #default="scope">
                      {{ formatVolume(scope.row.volume) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="change_percent" label="涨跌幅" min-width="80" show-overflow-tooltip>
                    <template #default="scope">
                      <span :class="getChangeClass(scope.row.change_percent)">
                        {{ formatPercent(scope.row.change_percent) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="88" fixed="right" align="center">
                    <template #default="scope">
                      <el-button type="danger" link @click="confirmDeleteHKIndexHistoricalRow(scope.row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <div class="pagination-section">
                  <el-pagination
                    v-model:current-page="hkIndexHistoricalCurrentPage"
                    v-model:page-size="hkIndexHistoricalPageSize"
                    :total="hkIndexHistoricalTotal"
                    :page-sizes="[20, 50, 100, 200]"
                    layout="total, sizes, prev, pager, next, jumper"
                    @size-change="handleHKIndexHistoricalPageSizeChange"
                    @current-change="handleHKIndexHistoricalPageChange"
                  />
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

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
                    <el-col :xs="24" :sm="24" :md="6" :lg="6" :xl="6">
                      <el-button type="danger" plain @click="openEtfRtDeleteDialog" :style="{ width: '100%' }">
                        删除实时行情
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
                  <el-table-column prop="trade_date" label="交易日" width="110" show-overflow-tooltip />
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
                  <el-table-column label="操作" width="88" fixed="right" align="center">
                    <template #default="scope">
                      <el-button type="danger" link @click="confirmDeleteEtfRealtimeRow(scope.row)">删除</el-button>
                    </template>
                  </el-table-column>
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
                    <el-col :xs="12" :sm="6" :md="3" :lg="3" :xl="3">
                      <el-button type="danger" plain @click="openEtfHistDeleteDialog" :style="{ width: '100%' }">
                        删除历史行情
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
                  <el-table-column label="操作" width="88" fixed="right" align="center">
                    <template #default="scope">
                      <el-button type="danger" link @click="confirmDeleteEtfHistoricalRow(scope.row)">删除</el-button>
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
      </el-tabs>
    </el-card>

    <el-dialog v-model="deleteHistoricalDialogVisible" title="删除 A 股历史行情" width="560px" @open="onDeleteHistoricalDialogOpen">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="mb-4"
        title="将物理删除 historical_quotes 表中的日线 K 线记录。可按单只股票、全部 A 股；可选 K 线日期区间。不选区间时：单股票表示删除该票全部历史日期；全部 A 股表示清空整张表。表格「删除」仅删除当前行对应的一条日线。"
      />
      <el-form label-width="120px">
        <el-form-item label="范围">
          <el-radio-group v-model="deleteHistoricalScope">
            <el-radio value="single">单个股票</el-radio>
            <el-radio value="all">全部 A 股</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="deleteHistoricalScope === 'single'" label="股票代码" required>
          <el-input v-model="deleteHistoricalCode" placeholder="如 600519" clearable />
        </el-form-item>
        <el-form-item label="K 线日期">
          <el-date-picker
            v-model="deleteHistoricalDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日"
            end-placeholder="结束日"
            value-format="YYYY-MM-DD"
            style="width: 100%"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deleteHistoricalDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="deleteHistoricalLoading" @click="submitDeleteHistorical">确定删除</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deleteIndexRealtimeDialogVisible" title="删除 A 股指数实时行情" width="560px" @open="onDeleteIndexRealtimeDialogOpen">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="mb-4"
        title="将物理删除 index_realtime_quotes 表中的数据。可按单个指数、全部指数删除；可选「更新时间」对应日期区间（取每条记录 update_time 的日期部分）；不选区间时单指数删该指数全部记录，全部指数则清空整张表。"
      />
      <el-form label-width="120px">
        <el-form-item label="范围">
          <el-radio-group v-model="deleteIndexRealtimeScope">
            <el-radio value="single">单个指数</el-radio>
            <el-radio value="all">全部 A 股指数</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="deleteIndexRealtimeScope === 'single'" label="指数代码" required>
          <el-input v-model="deleteIndexRealtimeCode" placeholder="如 000001" clearable />
        </el-form-item>
        <el-form-item label="更新时间（日期）">
          <el-date-picker
            v-model="deleteIndexRealtimeDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日"
            end-placeholder="结束日"
            value-format="YYYY-MM-DD"
            style="width: 100%"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deleteIndexRealtimeDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="deleteIndexRealtimeLoading" @click="submitDeleteIndexRealtime">确定删除</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="deleteIndustryRealtimeDialogVisible"
      title="删除 A 股行业板块实时行情"
      width="560px"
      @open="onDeleteIndustryRealtimeDialogOpen"
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="mb-4"
        title="将物理删除 industry_board_realtime_quotes 表中的数据。单个板块请填板块代码（如 BK0479）；可选「更新时间」的日期区间（取 update_time 前 10 位）。不选区间时：单板块删该板块全部记录；全部板块则清空整张表。"
      />
      <el-form label-width="120px">
        <el-form-item label="范围">
          <el-radio-group v-model="deleteIndustryRealtimeScope">
            <el-radio value="single">单个板块</el-radio>
            <el-radio value="all">全部板块</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="deleteIndustryRealtimeScope === 'single'" label="板块代码" required>
          <el-input v-model="deleteIndustryRealtimeCode" placeholder="如 BK0479" clearable />
        </el-form-item>
        <el-form-item label="更新时间（日期）">
          <el-date-picker
            v-model="deleteIndustryRealtimeDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日"
            end-placeholder="结束日"
            value-format="YYYY-MM-DD"
            style="width: 100%"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deleteIndustryRealtimeDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="deleteIndustryRealtimeLoading" @click="submitDeleteIndustryRealtime">确定删除</el-button>
      </template>
    </el-dialog>

    <!-- 港股：删除行情（4 个弹窗） -->
    <el-dialog v-model="hkStockRtDelVisible" title="删除港股实时行情" width="560px" @open="onHkStockRtDelOpen">
      <el-alert type="warning" :closable="false" show-icon class="mb-4"
        title="删除 stock_realtime_quote_hk。按交易日 trade_date 筛选；单个港股填代码（如 00700）；不选日期时单个表示删该股票全部交易日，全部港股表示清空整张表。" />
      <el-form label-width="120px">
        <el-form-item label="范围">
          <el-radio-group v-model="hkStockRtDelScope">
            <el-radio value="single">单个股票</el-radio>
            <el-radio value="all">全部港股</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="hkStockRtDelScope === 'single'" label="股票代码" required>
          <el-input v-model="hkStockRtDelCode" placeholder="如 00700" clearable />
        </el-form-item>
        <el-form-item label="交易日">
          <el-date-picker v-model="hkStockRtDelRange" type="daterange" range-separator="至" start-placeholder="开始日" end-placeholder="结束日"
            value-format="YYYY-MM-DD" style="width: 100%" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="hkStockRtDelVisible = false">取消</el-button>
        <el-button type="danger" :loading="hkStockRtDelLoading" @click="submitHkStockRtDelete">确定删除</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="hkStockHistDelVisible" title="删除港股历史行情" width="560px" @open="onHkStockHistDelOpen">
      <el-alert type="warning" :closable="false" show-icon class="mb-4"
        title="删除 historical_quotes_hk。按 K 线日期 date 筛选；不选日期时单个表示删该股票全部历史，全部表示清空整张表。" />
      <el-form label-width="120px">
        <el-form-item label="范围">
          <el-radio-group v-model="hkStockHistDelScope">
            <el-radio value="single">单个股票</el-radio>
            <el-radio value="all">全部港股</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="hkStockHistDelScope === 'single'" label="股票代码" required>
          <el-input v-model="hkStockHistDelCode" placeholder="如 00700" clearable />
        </el-form-item>
        <el-form-item label="K 线日期">
          <el-date-picker v-model="hkStockHistDelRange" type="daterange" range-separator="至" start-placeholder="开始日" end-placeholder="结束日"
            value-format="YYYY-MM-DD" style="width: 100%" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="hkStockHistDelVisible = false">取消</el-button>
        <el-button type="danger" :loading="hkStockHistDelLoading" @click="submitHkStockHistDelete">确定删除</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="hkIdxRtDelVisible" title="删除港股指数实时行情" width="560px" @open="onHkIdxRtDelOpen">
      <el-alert type="warning" :closable="false" show-icon class="mb-4"
        title="删除 hk_index_realtime_quotes。按交易日 trade_date 筛选；单个指数填代码；不选日期时单个删该指数全部记录，全部则清空整张表。" />
      <el-form label-width="120px">
        <el-form-item label="范围">
          <el-radio-group v-model="hkIdxRtDelScope">
            <el-radio value="single">单个指数</el-radio>
            <el-radio value="all">全部港股指数</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="hkIdxRtDelScope === 'single'" label="指数代码" required>
          <el-input v-model="hkIdxRtDelCode" placeholder="如 HSI" clearable />
        </el-form-item>
        <el-form-item label="交易日">
          <el-date-picker v-model="hkIdxRtDelRange" type="daterange" range-separator="至" start-placeholder="开始日" end-placeholder="结束日"
            value-format="YYYY-MM-DD" style="width: 100%" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="hkIdxRtDelVisible = false">取消</el-button>
        <el-button type="danger" :loading="hkIdxRtDelLoading" @click="submitHkIdxRtDelete">确定删除</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="hkIdxHistDelVisible" title="删除港股指数历史行情" width="560px" @open="onHkIdxHistDelOpen">
      <el-alert type="warning" :closable="false" show-icon class="mb-4"
        title="删除 hk_index_historical_quotes。按日期 date 筛选；不选日期时单个删该指数全部历史，全部则清空整张表。" />
      <el-form label-width="120px">
        <el-form-item label="范围">
          <el-radio-group v-model="hkIdxHistDelScope">
            <el-radio value="single">单个指数</el-radio>
            <el-radio value="all">全部港股指数</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="hkIdxHistDelScope === 'single'" label="指数代码" required>
          <el-input v-model="hkIdxHistDelCode" placeholder="如 HSI" clearable />
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="hkIdxHistDelRange" type="daterange" range-separator="至" start-placeholder="开始日" end-placeholder="结束日"
            value-format="YYYY-MM-DD" style="width: 100%" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="hkIdxHistDelVisible = false">取消</el-button>
        <el-button type="danger" :loading="hkIdxHistDelLoading" @click="submitHkIdxHistDelete">确定删除</el-button>
      </template>
    </el-dialog>

    <!-- ETF：删除行情 -->
    <el-dialog v-model="etfRtDelVisible" title="删除 ETF 实时行情" width="560px" @open="onEtfRtDelOpen">
      <el-alert type="warning" :closable="false" show-icon class="mb-4"
        title="删除 fund_realtime_quote。按交易日 trade_date 筛选；单个 ETF 填代码（如 510300）；不选日期时单个表示删该基金全部交易日记录，全部 ETF 表示清空整张表。" />
      <el-form label-width="120px">
        <el-form-item label="范围">
          <el-radio-group v-model="etfRtDelScope">
            <el-radio value="single">单个 ETF</el-radio>
            <el-radio value="all">全部 ETF</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="etfRtDelScope === 'single'" label="ETF 代码" required>
          <el-input v-model="etfRtDelCode" placeholder="如 510300" clearable />
        </el-form-item>
        <el-form-item label="交易日">
          <el-date-picker v-model="etfRtDelRange" type="daterange" range-separator="至" start-placeholder="开始日" end-placeholder="结束日"
            value-format="YYYY-MM-DD" style="width: 100%" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="etfRtDelVisible = false">取消</el-button>
        <el-button type="danger" :loading="etfRtDelLoading" @click="submitEtfRtDelete">确定删除</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="etfHistDelVisible" title="删除 ETF 历史行情" width="560px" @open="onEtfHistDelOpen">
      <el-alert type="warning" :closable="false" show-icon class="mb-4"
        title="删除 fund_historical_quotes。按 K 线日期 date 筛选；不选日期时单个表示删该基金全部历史，全部表示清空整张表。" />
      <el-form label-width="120px">
        <el-form-item label="范围">
          <el-radio-group v-model="etfHistDelScope">
            <el-radio value="single">单个 ETF</el-radio>
            <el-radio value="all">全部 ETF</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="etfHistDelScope === 'single'" label="ETF 代码" required>
          <el-input v-model="etfHistDelCode" placeholder="如 510300" clearable />
        </el-form-item>
        <el-form-item label="K 线日期">
          <el-date-picker v-model="etfHistDelRange" type="daterange" range-separator="至" start-placeholder="开始日" end-placeholder="结束日"
            value-format="YYYY-MM-DD" style="width: 100%" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="etfHistDelVisible = false">取消</el-button>
        <el-button type="danger" :loading="etfHistDelLoading" @click="submitEtfHistDelete">确定删除</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deleteRealtimeDialogVisible" title="删除 A 股实时行情" width="560px" @open="onDeleteRealtimeDialogOpen">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="mb-4"
        title="将物理删除 stock_realtime_quote 表中的数据。可按股票、按全部 A 股、并可限制交易日期范围；不选日期时，单个股票表示删该票全部日期，全部 A 股表示删整张表。"
      />
      <el-form label-width="120px">
        <el-form-item label="范围">
          <el-radio-group v-model="deleteRealtimeScope">
            <el-radio value="single">单个股票</el-radio>
            <el-radio value="all">全部 A 股</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="deleteRealtimeScope === 'single'" label="股票代码" required>
          <el-input v-model="deleteRealtimeCode" placeholder="如 600519" clearable />
        </el-form-item>
        <el-form-item label="交易日期">
          <el-date-picker
            v-model="deleteRealtimeDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日"
            end-placeholder="结束日"
            value-format="YYYY-MM-DD"
            style="width: 100%"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deleteRealtimeDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="deleteRealtimeLoading" @click="submitDeleteRealtime">确定删除</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="turnoverImportDialogVisible" title="A股实时行情换手率导入" width="640px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="支持 CSV/XLSX，必须包含 code(代码)、turnover_rate(换手率) 列；trade_date 可在文件列提供，或在下方统一指定。"
        class="mb-4"
      />
      <div class="mb-4">
        <el-button @click="downloadTurnoverTemplate('csv')">下载CSV模板</el-button>
        <el-button @click="downloadTurnoverTemplate('xlsx')">下载XLSX模板</el-button>
      </div>
      <el-form label-width="120px">
        <el-form-item label="统一交易日期">
          <el-date-picker
            v-model="turnoverImportTradeDate"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            placeholder="可选，不填则读取文件中的trade_date列"
          />
        </el-form-item>
        <el-form-item label="文件上传">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".csv,.xlsx,.xls"
            :show-file-list="true"
            :on-change="onTurnoverImportFileChange"
          >
            <template #trigger>
              <el-button>选择文件</el-button>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="Dry Run">
          <el-switch v-model="turnoverImportDryRun" />
        </el-form-item>
      </el-form>

      <el-card v-if="turnoverImportResult" class="mt-2">
        <template #header>导入结果</template>
        <div>
          总行数 {{ turnoverImportResult.total_rows }}，成功 {{ turnoverImportResult.success }}，
          跳过 {{ turnoverImportResult.skipped }}，失败 {{ turnoverImportResult.failed }}
        </div>
        <el-table :data="turnoverImportResult.failed_sample || []" size="small" class="mt-3">
          <el-table-column prop="row_no" label="行号" width="80" />
          <el-table-column prop="code" label="代码" width="120" />
          <el-table-column prop="message" label="错误信息" min-width="220" />
        </el-table>
      </el-card>

      <template #footer>
        <el-button @click="turnoverImportDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="turnoverImportLoading" @click="submitTurnoverImport">开始导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="historicalTurnoverImportDialogVisible" title="A股历史行情换手率更新" width="640px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="支持 CSV/XLSX，必须包含 code(代码)、turnover_rate(换手率) 列；trade_date 可在文件列提供，或在下方统一指定。"
        class="mb-4"
      />
      <div class="mb-4">
        <el-button @click="downloadTurnoverTemplate('csv')">下载CSV模板</el-button>
        <el-button @click="downloadTurnoverTemplate('xlsx')">下载XLSX模板</el-button>
      </div>
      <el-form label-width="120px">
        <el-form-item label="统一交易日期">
          <el-date-picker
            v-model="historicalTurnoverImportTradeDate"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            placeholder="可选，不填则读取文件中的trade_date列"
          />
        </el-form-item>
        <el-form-item label="文件上传">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".csv,.xlsx,.xls"
            :show-file-list="true"
            :on-change="onHistoricalTurnoverImportFileChange"
          >
            <template #trigger>
              <el-button>选择文件</el-button>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="Dry Run">
          <el-switch v-model="historicalTurnoverImportDryRun" />
        </el-form-item>
      </el-form>

      <el-card v-if="historicalTurnoverImportResult" class="mt-2">
        <template #header>导入结果</template>
        <div>
          总行数 {{ historicalTurnoverImportResult.total_rows }}，成功 {{ historicalTurnoverImportResult.success }}，
          跳过 {{ historicalTurnoverImportResult.skipped }}，失败 {{ historicalTurnoverImportResult.failed }}
        </div>
        <el-table :data="historicalTurnoverImportResult.failed_sample || []" size="small" class="mt-3">
          <el-table-column prop="row_no" label="行号" width="80" />
          <el-table-column prop="code" label="代码" width="120" />
          <el-table-column prop="message" label="错误信息" min-width="220" />
        </el-table>
      </el-card>

      <template #footer>
        <el-button @click="historicalTurnoverImportDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="historicalTurnoverImportLoading" @click="submitHistoricalTurnoverImport">开始更新</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="exportDialogVisible"
      :title="exportForm.market === 'CN' ? '导出A股历史行情数据' : '导出港股历史行情数据'"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="exportFormRef"
        :model="exportForm"
        :rules="exportRules"
        label-width="100px"
      >
        <el-form-item label="日期选择">
          <el-radio-group v-model="exportForm.dateType">
            <el-radio value="single">指定单日</el-radio>
            <el-radio value="range">指定区间</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item v-if="exportForm.dateType === 'single'" label="选择日期" prop="date">
          <el-date-picker
            v-model="exportForm.date"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item v-if="exportForm.dateType === 'range'" label="开始日期" prop="startDate">
          <el-date-picker
            v-model="exportForm.startDate"
            type="date"
            placeholder="开始日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item v-if="exportForm.dateType === 'range'" label="结束日期" prop="endDate">
          <el-date-picker
            v-model="exportForm.endDate"
            type="date"
            placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="导出格式" prop="format">
          <el-radio-group v-model="exportForm.format">
            <el-radio value="xlsx">Excel (.xlsx)</el-radio>
            <el-radio value="txt">文本 (.txt)</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="exportDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitExport" :loading="exportLoading">
            确定导出
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElLoading, ElMessageBox } from 'element-plus'
import { Refresh, Search, Download } from '@element-plus/icons-vue'
import { quotesService } from '@/services/quotes.service'

// 主标签和子标签
const mainTab = ref('a-share')
const aShareTab = ref('stocks')
const hkShareTab = ref('hk-stocks')
const loading = ref(false)

// A股股票数据
const stockData = ref<any[]>([])
const stockLoading = ref(false)
const stockCurrentPage = ref(1)
const stockPageSize = ref(20)
const stockTotal = ref(0)
const stockSearchKeyword = ref('')
const stockMarketFilter = ref('')
const stockSortBy = ref('update_time')
const turnoverImportDialogVisible = ref(false)
const turnoverImportTradeDate = ref('')
const turnoverImportFile = ref<File | null>(null)
const turnoverImportLoading = ref(false)
const turnoverImportDryRun = ref(false)
const turnoverImportResult = ref<any>(null)
const historicalTurnoverImportDialogVisible = ref(false)
const historicalTurnoverImportTradeDate = ref('')
const historicalTurnoverImportFile = ref<File | null>(null)
const historicalTurnoverImportLoading = ref(false)
const historicalTurnoverImportDryRun = ref(false)
const historicalTurnoverImportResult = ref<any>(null)

const deleteRealtimeDialogVisible = ref(false)
const deleteRealtimeLoading = ref(false)
const deleteRealtimeScope = ref<'single' | 'all'>('single')
const deleteRealtimeCode = ref('')
const deleteRealtimeDateRange = ref<[string, string] | null>(null)

const deleteIndexRealtimeDialogVisible = ref(false)
const deleteIndexRealtimeLoading = ref(false)
const deleteIndexRealtimeScope = ref<'single' | 'all'>('single')
const deleteIndexRealtimeCode = ref('')
const deleteIndexRealtimeDateRange = ref<[string, string] | null>(null)

const deleteIndustryRealtimeDialogVisible = ref(false)
const deleteIndustryRealtimeLoading = ref(false)
const deleteIndustryRealtimeScope = ref<'single' | 'all'>('single')
const deleteIndustryRealtimeCode = ref('')
const deleteIndustryRealtimeDateRange = ref<[string, string] | null>(null)

const hkStockRtDelVisible = ref(false)
const hkStockRtDelLoading = ref(false)
const hkStockRtDelScope = ref<'single' | 'all'>('single')
const hkStockRtDelCode = ref('')
const hkStockRtDelRange = ref<[string, string] | null>(null)

const hkStockHistDelVisible = ref(false)
const hkStockHistDelLoading = ref(false)
const hkStockHistDelScope = ref<'single' | 'all'>('single')
const hkStockHistDelCode = ref('')
const hkStockHistDelRange = ref<[string, string] | null>(null)

const hkIdxRtDelVisible = ref(false)
const hkIdxRtDelLoading = ref(false)
const hkIdxRtDelScope = ref<'single' | 'all'>('single')
const hkIdxRtDelCode = ref('')
const hkIdxRtDelRange = ref<[string, string] | null>(null)

const hkIdxHistDelVisible = ref(false)
const hkIdxHistDelLoading = ref(false)
const hkIdxHistDelScope = ref<'single' | 'all'>('single')
const hkIdxHistDelCode = ref('')
const hkIdxHistDelRange = ref<[string, string] | null>(null)

const etfRtDelVisible = ref(false)
const etfRtDelLoading = ref(false)
const etfRtDelScope = ref<'single' | 'all'>('single')
const etfRtDelCode = ref('')
const etfRtDelRange = ref<[string, string] | null>(null)

const etfHistDelVisible = ref(false)
const etfHistDelLoading = ref(false)
const etfHistDelScope = ref<'single' | 'all'>('single')
const etfHistDelCode = ref('')
const etfHistDelRange = ref<[string, string] | null>(null)

const deleteHistoricalDialogVisible = ref(false)
const deleteHistoricalLoading = ref(false)
const deleteHistoricalScope = ref<'single' | 'all'>('single')
const deleteHistoricalCode = ref('')
const deleteHistoricalDateRange = ref<[string, string] | null>(null)

// A股指数数据
const indexData = ref<any[]>([])
const indexLoading = ref(false)
const indexCurrentPage = ref(1)
const indexPageSize = ref(20)
const indexTotal = ref(0)
const indexSearchKeyword = ref('')

// A股历史行情数据
const historicalData = ref<any[]>([])
const historicalLoading = ref(false)
const historicalCurrentPage = ref(1)
const historicalPageSize = ref(20)
const historicalTotal = ref(0)
const historicalSearchKeyword = ref('')
const historicalStartDate = ref('')
const historicalEndDate = ref('')
const historicalPeriod = ref('daily')

// 导出功能状态
const exportDialogVisible = ref(false)
const exportLoading = ref(false)
const exportFormRef = ref<FormInstance>()
const exportForm = reactive({
  dateType: 'single', // 'single' | 'range'
  date: '',
  startDate: '',
  endDate: '',
  format: 'xlsx' as 'txt' | 'xlsx',
  market: 'CN' as 'CN' | 'HK'
})
const exportRules = reactive<FormRules>({
  date: [
    { 
      required: true, 
      message: '请选择指定日期', 
      trigger: 'change',
      validator: (_rule, value, callback) => {
        if (exportForm.dateType === 'single' && !value) callback(new Error('请选择指定日期'))
        else callback()
      }
    }
  ],
  startDate: [
    { 
      required: true, 
      message: '请选择开始日期', 
      trigger: 'change',
      validator: (_rule, value, callback) => {
        if (exportForm.dateType === 'range' && !value) callback(new Error('请选择开始日期'))
        else callback()
      }
    }
  ],
  endDate: [
    { 
      required: true, 
      message: '请选择结束日期', 
      trigger: 'change',
      validator: (_rule, value, callback) => {
        if (exportForm.dateType === 'range' && !value) callback(new Error('请选择结束日期'))
        else callback()
      }
    }
  ]
})

// A股行业板块数据
const industryData = ref<any[]>([])
const industryLoading = ref(false)
const industryCurrentPage = ref(1)
const industryPageSize = ref(20)
const industryTotal = ref(0)
const industrySearchKeyword = ref('')

// 港股股票数据
const hkStockData = ref<any[]>([])
const hkStockLoading = ref(false)
const hkStockCurrentPage = ref(1)
const hkStockPageSize = ref(20)
const hkStockTotal = ref(0)
const hkStockSearchKeyword = ref('')

// 港股历史行情数据
const hkHistoricalData = ref<any[]>([])
const hkHistoricalLoading = ref(false)
const hkHistoricalCurrentPage = ref(1)
const hkHistoricalPageSize = ref(20)
const hkHistoricalTotal = ref(0)
const hkHistoricalSearchKeyword = ref('')
const hkHistoricalStartDate = ref('')
const hkHistoricalEndDate = ref('')

// 港股指数数据
const hkIndexData = ref<any[]>([])
const hkIndexLoading = ref(false)
const hkIndexCurrentPage = ref(1)
const hkIndexPageSize = ref(20)
const hkIndexTotal = ref(0)
const hkIndexSearchKeyword = ref('')

// 港股指数历史行情数据
const hkIndexHistoricalData = ref<any[]>([])
const hkIndexHistoricalLoading = ref(false)
const hkIndexHistoricalCurrentPage = ref(1)
const hkIndexHistoricalPageSize = ref(20)
const hkIndexHistoricalTotal = ref(0)
const hkIndexHistoricalSearchKeyword = ref('')
const hkIndexHistoricalStartDate = ref('')
const hkIndexHistoricalEndDate = ref('')

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

// 格式化函数
const formatPrice = (value: any) => {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toFixed(2)
}

const formatPercent = (value: any) => {
  if (value === null || value === undefined || value === '') return '-'
  return `${Number(value).toFixed(2)}%`
}

// 成交量库存为手；按手显示：万手/亿手
const formatVolume = (value: any) => {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  if (num >= 100000000) return `${(num / 100000000).toFixed(2)}亿`
  if (num >= 10000) return `${(num / 10000).toFixed(2)}万`
  return `${num.toFixed(0)}`
}

const formatAmount = (value: any) => {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  if (num >= 100000000) return `${(num / 100000000).toFixed(2)}亿`
  if (num >= 10000) return `${(num / 10000).toFixed(2)}万`
  return num.toFixed(2)
}

const getPriceClass = (current: any, preClose: any) => {
  if (!current || !preClose) return ''
  const diff = Number(current) - Number(preClose)
  if (diff > 0) return 'price-up'
  if (diff < 0) return 'price-down'
  return ''
}

const getChangeClass = (value: any) => {
  if (value === null || value === undefined || value === '') return ''
  const num = Number(value)
  if (num > 0) return 'price-up'
  if (num < 0) return 'price-down'
  return ''
}

// 主标签切换

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

const handleMainTabChange = (tab: any) => {
  console.log('Main tab changed:', tab)
  if (tab === 'a-share') {
    handleAShareTabChange(aShareTab.value)
  } else if (tab === 'hk-share') {
    if (hkStockData.value.length === 0) fetchHKStockData()
  } else if (tab === 'etf-data') {
    if (etfData.value.length === 0) fetchETFData()
  } else if (tab === 'never_used_dummy_to_keep_original_code') {
    handleHKShareTabChange(hkShareTab.value)
  }
}

// A股子标签切换
const handleAShareTabChange = (tab: any) => {
  console.log('A-share tab changed:', tab)
  switch (tab) {
    case 'stocks':
      fetchStockData()
      break
    case 'indices':
      fetchIndexData()
      break
    case 'historical':
      fetchHistoricalData()
      break
    case 'industries':
      fetchIndustryData()
      break
  }
}

// 港股子标签切换
const handleHKShareTabChange = (tab: any) => {
  console.log('HK-share tab changed:', tab)
  switch (tab) {
    case 'hk-stocks':
      fetchHKStockData()
      break
    case 'hk-historical':
      fetchHKHistoricalData()
      break
    case 'hk-indices':
      fetchHKIndexData()
      break
    case 'hk-index-historical':
      fetchHKIndexHistoricalData()
      break
  }
}

// 辅助函数：显示全屏加载
const showLoading = () => {
  return ElLoading.service({
    lock: true,
    text: '查询进行时...',
    background: 'rgba(0, 0, 0, 0.7)',
  })
}

// 刷新所有数据
const refreshAllData = async () => {
  loading.value = true
  const loadingInstance = showLoading()
  try {
        if (mainTab.value === 'etf-data') {
      if (etfTab.value === 'etf-stocks') fetchETFData()
      else if (etfTab.value === 'etf-historical') fetchETFHistoricalData()
    }
    else if (mainTab.value === 'a-share') {
      await handleAShareTabChange(aShareTab.value)
    } else {
      await handleHKShareTabChange(hkShareTab.value)
    }
    ElMessage.success('数据刷新成功')
  } catch (error) {
    console.error('刷新数据失败:', error)
    ElMessage.error('数据刷新失败')
  } finally {
    loading.value = false
    loadingInstance.close()
  }
}

// A股股票数据获取
const fetchStockData = async () => {
  stockLoading.value = true
  const loadingInstance = showLoading()
  try {
    const response = await quotesService.getStockQuotes({
      page: stockCurrentPage.value,
      pageSize: stockPageSize.value,
      keyword: stockSearchKeyword.value,
      market: stockMarketFilter.value,
      sortBy: stockSortBy.value
    })
    
    if (response.success) {
      stockData.value = response.data
      stockTotal.value = response.total
    }
  } catch (error) {
    console.error('获取股票数据失败:', error)
    ElMessage.error('获取股票数据失败')
  } finally {
    stockLoading.value = false
    loadingInstance.close()
  }
}

const refreshStockData = () => fetchStockData()
const handleStockSearch = () => {
  stockCurrentPage.value = 1
  fetchStockData()
}
const handleStockMarketFilter = () => {
  stockCurrentPage.value = 1
  fetchStockData()
}
const handleStockSortChange = () => fetchStockData()
const handleStockPageChange = () => fetchStockData()
const handleStockPageSizeChange = () => {
  stockCurrentPage.value = 1
  fetchStockData()
}

const openDeleteRealtimeDialog = () => {
  deleteRealtimeDialogVisible.value = true
}

const onDeleteRealtimeDialogOpen = () => {
  deleteRealtimeScope.value = 'single'
  deleteRealtimeCode.value = ''
  deleteRealtimeDateRange.value = null
}

const submitDeleteRealtime = async () => {
  if (deleteRealtimeScope.value === 'single' && !deleteRealtimeCode.value.trim()) {
    ElMessage.warning('请填写股票代码')
    return
  }
  const range = deleteRealtimeDateRange.value
  const startDate = range?.[0]
  const endDate = range?.[1]
  if (deleteRealtimeScope.value === 'all' && !startDate && !endDate) {
    try {
      await ElMessageBox.confirm(
        '将删除 A 股实时行情表（stock_realtime_quote）中的全部记录，所有股票、所有交易日。此操作不可恢复，是否继续？',
        '危险操作',
        { type: 'error', confirmButtonText: '仍要删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm('确定按上述条件删除实时行情数据吗？此操作不可恢复。', '删除确认', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }

  deleteRealtimeLoading.value = true
  try {
    const res = await quotesService.deleteAshareRealtimeQuotes({
      scope: deleteRealtimeScope.value,
      code: deleteRealtimeScope.value === 'single' ? deleteRealtimeCode.value.trim() : undefined,
      startDate,
      endDate
    })
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
      deleteRealtimeDialogVisible.value = false
      await fetchStockData()
    } else {
      ElMessage.warning(res.message || '删除未完成')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '删除失败')
  } finally {
    deleteRealtimeLoading.value = false
  }
}

const confirmDeleteStockRow = (row: { code?: string; name?: string }) => {
  const code = row?.code || ''
  const name = row?.name || ''
  ElMessageBox.confirm(
    `确定删除股票 ${code} ${name} 在实时行情表中的全部记录（所有交易日）吗？不可恢复。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
    .then(async () => {
      const res = await quotesService.deleteAshareRealtimeQuotes({ scope: 'single', code })
      if (res.success) {
        ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
        await fetchStockData()
      }
    })
    .catch(() => {})
}

const openDeleteIndexRealtimeDialog = () => {
  deleteIndexRealtimeDialogVisible.value = true
}

const onDeleteIndexRealtimeDialogOpen = () => {
  deleteIndexRealtimeScope.value = 'single'
  deleteIndexRealtimeCode.value = ''
  deleteIndexRealtimeDateRange.value = null
}

const submitDeleteIndexRealtime = async () => {
  if (deleteIndexRealtimeScope.value === 'single' && !deleteIndexRealtimeCode.value.trim()) {
    ElMessage.warning('请填写指数代码')
    return
  }
  const range = deleteIndexRealtimeDateRange.value
  const startDate = range?.[0]
  const endDate = range?.[1]
  if (deleteIndexRealtimeScope.value === 'all' && !startDate && !endDate) {
    try {
      await ElMessageBox.confirm(
        '将删除指数实时行情表（index_realtime_quotes）中的全部记录，所有指数。此操作不可恢复，是否继续？',
        '危险操作',
        { type: 'error', confirmButtonText: '仍要删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm('确定按上述条件删除指数实时行情数据吗？此操作不可恢复。', '删除确认', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }

  deleteIndexRealtimeLoading.value = true
  try {
    const res = await quotesService.deleteAshareIndexRealtimeQuotes({
      scope: deleteIndexRealtimeScope.value,
      code: deleteIndexRealtimeScope.value === 'single' ? deleteIndexRealtimeCode.value.trim() : undefined,
      startDate,
      endDate
    })
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
      deleteIndexRealtimeDialogVisible.value = false
      await fetchIndexData()
    } else {
      ElMessage.warning(res.message || '删除未完成')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '删除失败')
  } finally {
    deleteIndexRealtimeLoading.value = false
  }
}

const confirmDeleteIndexRow = (row: { code?: string; name?: string }) => {
  const code = row?.code || ''
  const name = row?.name || ''
  ElMessageBox.confirm(
    `确定删除指数 ${code} ${name} 在 index_realtime_quotes 中的全部记录吗？不可恢复。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
    .then(async () => {
      const res = await quotesService.deleteAshareIndexRealtimeQuotes({ scope: 'single', code })
      if (res.success) {
        ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
        await fetchIndexData()
      }
    })
    .catch(() => {})
}

const openDeleteIndustryRealtimeDialog = () => {
  deleteIndustryRealtimeDialogVisible.value = true
}

const onDeleteIndustryRealtimeDialogOpen = () => {
  deleteIndustryRealtimeScope.value = 'single'
  deleteIndustryRealtimeCode.value = ''
  deleteIndustryRealtimeDateRange.value = null
}

const submitDeleteIndustryRealtime = async () => {
  if (deleteIndustryRealtimeScope.value === 'single' && !deleteIndustryRealtimeCode.value.trim()) {
    ElMessage.warning('请填写板块代码')
    return
  }
  const range = deleteIndustryRealtimeDateRange.value
  const startDate = range?.[0]
  const endDate = range?.[1]
  if (deleteIndustryRealtimeScope.value === 'all' && !startDate && !endDate) {
    try {
      await ElMessageBox.confirm(
        '将删除行业板块实时行情表（industry_board_realtime_quotes）中的全部记录。此操作不可恢复，是否继续？',
        '危险操作',
        { type: 'error', confirmButtonText: '仍要删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm('确定按上述条件删除行业板块实时行情吗？此操作不可恢复。', '删除确认', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }

  deleteIndustryRealtimeLoading.value = true
  try {
    const res = await quotesService.deleteAshareIndustryRealtimeQuotes({
      scope: deleteIndustryRealtimeScope.value,
      code: deleteIndustryRealtimeScope.value === 'single' ? deleteIndustryRealtimeCode.value.trim() : undefined,
      startDate,
      endDate
    })
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
      deleteIndustryRealtimeDialogVisible.value = false
      await fetchIndustryData()
    } else {
      ElMessage.warning(res.message || '删除未完成')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '删除失败')
  } finally {
    deleteIndustryRealtimeLoading.value = false
  }
}

const confirmDeleteIndustryRow = (row: { board_code?: string; board_name?: string }) => {
  const code = row?.board_code || ''
  const name = row?.board_name || ''
  ElMessageBox.confirm(
    `确定删除板块 ${code} ${name} 在 industry_board_realtime_quotes 中的全部记录吗？不可恢复。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
    .then(async () => {
      const res = await quotesService.deleteAshareIndustryRealtimeQuotes({ scope: 'single', code })
      if (res.success) {
        ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
        await fetchIndustryData()
      }
    })
    .catch(() => {})
}

const openDeleteHistoricalDialog = () => {
  deleteHistoricalDialogVisible.value = true
}

const onDeleteHistoricalDialogOpen = () => {
  deleteHistoricalScope.value = 'single'
  deleteHistoricalCode.value = ''
  deleteHistoricalDateRange.value = null
}

const submitDeleteHistorical = async () => {
  if (deleteHistoricalScope.value === 'single' && !deleteHistoricalCode.value.trim()) {
    ElMessage.warning('请填写股票代码')
    return
  }
  const range = deleteHistoricalDateRange.value
  const startDate = range?.[0]
  const endDate = range?.[1]
  if (deleteHistoricalScope.value === 'all' && !startDate && !endDate) {
    try {
      await ElMessageBox.confirm(
        '将删除历史行情表（historical_quotes）中的全部日线记录，所有股票。此操作不可恢复，是否继续？',
        '危险操作',
        { type: 'error', confirmButtonText: '仍要删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm('确定按上述条件删除历史行情数据吗？此操作不可恢复。', '删除确认', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }

  deleteHistoricalLoading.value = true
  try {
    const res = await quotesService.deleteAshareHistoricalQuotes({
      scope: deleteHistoricalScope.value,
      code: deleteHistoricalScope.value === 'single' ? deleteHistoricalCode.value.trim() : undefined,
      startDate,
      endDate
    })
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
      deleteHistoricalDialogVisible.value = false
      await fetchHistoricalData()
    } else {
      ElMessage.warning(res.message || '删除未完成')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '删除失败')
  } finally {
    deleteHistoricalLoading.value = false
  }
}

/** 将接口返回的 date 格式化为 YYYY-MM-DD */
const formatHistoricalRowDate = (d: unknown): string => {
  if (d == null || d === '') return ''
  if (typeof d === 'string') return d.length >= 10 ? d.slice(0, 10) : d
  return String(d)
}

const confirmDeleteHistoricalRow = (row: { code?: string; name?: string; date?: unknown }) => {
  const code = row?.code || ''
  const name = row?.name || ''
  const day = formatHistoricalRowDate(row?.date)
  if (!code || !day) {
    ElMessage.warning('当前行缺少代码或日期，无法删除')
    return
  }
  ElMessageBox.confirm(
    `确定删除 ${code} ${name} 在 ${day} 这一天的历史行情记录吗？不可恢复。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
    .then(async () => {
      const res = await quotesService.deleteAshareHistoricalQuotes({
        scope: 'single',
        code,
        startDate: day,
        endDate: day
      })
      if (res.success) {
        ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
        await fetchHistoricalData()
      }
    })
    .catch(() => {})
}

// —— 港股：删除行情 ——
const openHkStockRtDeleteDialog = () => {
  hkStockRtDelVisible.value = true
}
const onHkStockRtDelOpen = () => {
  hkStockRtDelScope.value = 'single'
  hkStockRtDelCode.value = ''
  hkStockRtDelRange.value = null
}
const submitHkStockRtDelete = async () => {
  if (hkStockRtDelScope.value === 'single' && !hkStockRtDelCode.value.trim()) {
    ElMessage.warning('请填写股票代码')
    return
  }
  const range = hkStockRtDelRange.value
  const startDate = range?.[0]
  const endDate = range?.[1]
  if (hkStockRtDelScope.value === 'all' && !startDate && !endDate) {
    try {
      await ElMessageBox.confirm(
        '将清空港股实时行情表 stock_realtime_quote_hk 的全部记录，是否继续？',
        '危险操作',
        { type: 'error', confirmButtonText: '仍要删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm('确定按上述条件删除港股实时行情吗？此操作不可恢复。', '删除确认', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }
  hkStockRtDelLoading.value = true
  try {
    const res = await quotesService.deleteHKStockRealtimeQuotes({
      scope: hkStockRtDelScope.value,
      code: hkStockRtDelScope.value === 'single' ? hkStockRtDelCode.value.trim() : undefined,
      startDate,
      endDate
    })
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
      hkStockRtDelVisible.value = false
      await fetchHKStockData()
    } else {
      ElMessage.warning(res.message || '删除未完成')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '删除失败')
  } finally {
    hkStockRtDelLoading.value = false
  }
}
const confirmDeleteHKStockRealtimeRow = (row: { code?: string; name?: string; trade_date?: unknown }) => {
  const code = row?.code || ''
  const name = row?.name || ''
  const day = formatHistoricalRowDate(row?.trade_date)
  if (!code) {
    ElMessage.warning('当前行缺少股票代码')
    return
  }
  const msg = day
    ? `确定删除 ${code} ${name} 在交易日 ${day} 的港股实时记录吗？`
    : `当前行无交易日字段，将删除 ${code} ${name} 在库中的全部港股实时记录。是否继续？`
  ElMessageBox.confirm(msg, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
    .then(async () => {
      const res = day
        ? await quotesService.deleteHKStockRealtimeQuotes({
            scope: 'single',
            code,
            startDate: day,
            endDate: day
          })
        : await quotesService.deleteHKStockRealtimeQuotes({ scope: 'single', code })
      if (res.success) {
        ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
        await fetchHKStockData()
      }
    })
    .catch(() => {})
}

const openHkStockHistDeleteDialog = () => {
  hkStockHistDelVisible.value = true
}
const onHkStockHistDelOpen = () => {
  hkStockHistDelScope.value = 'single'
  hkStockHistDelCode.value = ''
  hkStockHistDelRange.value = null
}
const submitHkStockHistDelete = async () => {
  if (hkStockHistDelScope.value === 'single' && !hkStockHistDelCode.value.trim()) {
    ElMessage.warning('请填写股票代码')
    return
  }
  const range = hkStockHistDelRange.value
  const startDate = range?.[0]
  const endDate = range?.[1]
  if (hkStockHistDelScope.value === 'all' && !startDate && !endDate) {
    try {
      await ElMessageBox.confirm(
        '将清空港股历史行情表 historical_quotes_hk 的全部记录，是否继续？',
        '危险操作',
        { type: 'error', confirmButtonText: '仍要删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm('确定按上述条件删除港股历史行情吗？此操作不可恢复。', '删除确认', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }
  hkStockHistDelLoading.value = true
  try {
    const res = await quotesService.deleteHKStockHistoricalQuotes({
      scope: hkStockHistDelScope.value,
      code: hkStockHistDelScope.value === 'single' ? hkStockHistDelCode.value.trim() : undefined,
      startDate,
      endDate
    })
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
      hkStockHistDelVisible.value = false
      await fetchHKHistoricalData()
    } else {
      ElMessage.warning(res.message || '删除未完成')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '删除失败')
  } finally {
    hkStockHistDelLoading.value = false
  }
}
const confirmDeleteHKHistoricalStockRow = (row: { code?: string; name?: string; date?: unknown }) => {
  const code = row?.code || ''
  const name = row?.name || ''
  const day = formatHistoricalRowDate(row?.date)
  if (!code || !day) {
    ElMessage.warning('当前行缺少代码或日期')
    return
  }
  ElMessageBox.confirm(
    `确定删除 ${code} ${name} 在 ${day} 的港股历史记录吗？`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
    .then(async () => {
      const res = await quotesService.deleteHKStockHistoricalQuotes({
        scope: 'single',
        code,
        startDate: day,
        endDate: day
      })
      if (res.success) {
        ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
        await fetchHKHistoricalData()
      }
    })
    .catch(() => {})
}

const openHkIdxRtDeleteDialog = () => {
  hkIdxRtDelVisible.value = true
}
const onHkIdxRtDelOpen = () => {
  hkIdxRtDelScope.value = 'single'
  hkIdxRtDelCode.value = ''
  hkIdxRtDelRange.value = null
}
const submitHkIdxRtDelete = async () => {
  if (hkIdxRtDelScope.value === 'single' && !hkIdxRtDelCode.value.trim()) {
    ElMessage.warning('请填写指数代码')
    return
  }
  const range = hkIdxRtDelRange.value
  const startDate = range?.[0]
  const endDate = range?.[1]
  if (hkIdxRtDelScope.value === 'all' && !startDate && !endDate) {
    try {
      await ElMessageBox.confirm(
        '将清空港股指数实时行情表 hk_index_realtime_quotes 的全部记录，是否继续？',
        '危险操作',
        { type: 'error', confirmButtonText: '仍要删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm('确定按上述条件删除港股指数实时行情吗？此操作不可恢复。', '删除确认', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }
  hkIdxRtDelLoading.value = true
  try {
    const res = await quotesService.deleteHKIndexRealtimeQuotes({
      scope: hkIdxRtDelScope.value,
      code: hkIdxRtDelScope.value === 'single' ? hkIdxRtDelCode.value.trim() : undefined,
      startDate,
      endDate
    })
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
      hkIdxRtDelVisible.value = false
      await fetchHKIndexData()
    } else {
      ElMessage.warning(res.message || '删除未完成')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '删除失败')
  } finally {
    hkIdxRtDelLoading.value = false
  }
}
const confirmDeleteHKIndexRealtimeRow = (row: { code?: string; name?: string; trade_date?: unknown }) => {
  const code = row?.code || ''
  const name = row?.name || ''
  const day = formatHistoricalRowDate(row?.trade_date)
  if (!code) {
    ElMessage.warning('当前行缺少指数代码')
    return
  }
  const msg = day
    ? `确定删除指数 ${code} ${name} 在交易日 ${day} 的实时记录吗？`
    : `当前行无交易日字段，将删除 ${code} ${name} 在库中的全部港股指数实时记录。是否继续？`
  ElMessageBox.confirm(msg, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
    .then(async () => {
      const res = day
        ? await quotesService.deleteHKIndexRealtimeQuotes({
            scope: 'single',
            code,
            startDate: day,
            endDate: day
          })
        : await quotesService.deleteHKIndexRealtimeQuotes({ scope: 'single', code })
      if (res.success) {
        ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
        await fetchHKIndexData()
      }
    })
    .catch(() => {})
}

const openHkIdxHistDeleteDialog = () => {
  hkIdxHistDelVisible.value = true
}
const onHkIdxHistDelOpen = () => {
  hkIdxHistDelScope.value = 'single'
  hkIdxHistDelCode.value = ''
  hkIdxHistDelRange.value = null
}
const submitHkIdxHistDelete = async () => {
  if (hkIdxHistDelScope.value === 'single' && !hkIdxHistDelCode.value.trim()) {
    ElMessage.warning('请填写指数代码')
    return
  }
  const range = hkIdxHistDelRange.value
  const startDate = range?.[0]
  const endDate = range?.[1]
  if (hkIdxHistDelScope.value === 'all' && !startDate && !endDate) {
    try {
      await ElMessageBox.confirm(
        '将清空港股指数历史行情表 hk_index_historical_quotes 的全部记录，是否继续？',
        '危险操作',
        { type: 'error', confirmButtonText: '仍要删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm('确定按上述条件删除港股指数历史行情吗？此操作不可恢复。', '删除确认', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }
  hkIdxHistDelLoading.value = true
  try {
    const res = await quotesService.deleteHKIndexHistoricalQuotes({
      scope: hkIdxHistDelScope.value,
      code: hkIdxHistDelScope.value === 'single' ? hkIdxHistDelCode.value.trim() : undefined,
      startDate,
      endDate
    })
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
      hkIdxHistDelVisible.value = false
      await fetchHKIndexHistoricalData()
    } else {
      ElMessage.warning(res.message || '删除未完成')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '删除失败')
  } finally {
    hkIdxHistDelLoading.value = false
  }
}
const confirmDeleteHKIndexHistoricalRow = (row: { code?: string; name?: string; date?: unknown }) => {
  const code = row?.code || ''
  const name = row?.name || ''
  const day = formatHistoricalRowDate(row?.date)
  if (!code || !day) {
    ElMessage.warning('当前行缺少代码或日期')
    return
  }
  ElMessageBox.confirm(`确定删除指数 ${code} ${name} 在 ${day} 的历史记录吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
    .then(async () => {
      const res = await quotesService.deleteHKIndexHistoricalQuotes({
        scope: 'single',
        code,
        startDate: day,
        endDate: day
      })
      if (res.success) {
        ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
        await fetchHKIndexHistoricalData()
      }
    })
    .catch(() => {})
}

// —— ETF：删除行情 ——
const openEtfRtDeleteDialog = () => {
  etfRtDelVisible.value = true
}
const onEtfRtDelOpen = () => {
  etfRtDelScope.value = 'single'
  etfRtDelCode.value = ''
  etfRtDelRange.value = null
}
const submitEtfRtDelete = async () => {
  if (etfRtDelScope.value === 'single' && !etfRtDelCode.value.trim()) {
    ElMessage.warning('请填写 ETF 代码')
    return
  }
  const range = etfRtDelRange.value
  const startDate = range?.[0]
  const endDate = range?.[1]
  if (etfRtDelScope.value === 'all' && !startDate && !endDate) {
    try {
      await ElMessageBox.confirm(
        '将清空 ETF 实时行情表 fund_realtime_quote 的全部记录，是否继续？',
        '危险操作',
        { type: 'error', confirmButtonText: '仍要删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm('确定按上述条件删除 ETF 实时行情吗？此操作不可恢复。', '删除确认', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }
  etfRtDelLoading.value = true
  try {
    const res = await quotesService.deleteETFRealtimeQuotes({
      scope: etfRtDelScope.value,
      code: etfRtDelScope.value === 'single' ? etfRtDelCode.value.trim() : undefined,
      startDate,
      endDate
    })
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
      etfRtDelVisible.value = false
      await fetchETFData()
    } else {
      ElMessage.warning(res.message || '删除未完成')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '删除失败')
  } finally {
    etfRtDelLoading.value = false
  }
}
const confirmDeleteEtfRealtimeRow = (row: { code?: string; name?: string; trade_date?: unknown }) => {
  const code = row?.code || ''
  const name = row?.name || ''
  const day = formatHistoricalRowDate(row?.trade_date)
  if (!code) {
    ElMessage.warning('当前行缺少 ETF 代码')
    return
  }
  const msg = day
    ? `确定删除 ${code} ${name} 在交易日 ${day} 的 ETF 实时记录吗？`
    : `当前行无交易日字段，将删除 ${code} ${name} 在库中的全部 ETF 实时记录。是否继续？`
  ElMessageBox.confirm(msg, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
    .then(async () => {
      const res = day
        ? await quotesService.deleteETFRealtimeQuotes({
            scope: 'single',
            code,
            startDate: day,
            endDate: day
          })
        : await quotesService.deleteETFRealtimeQuotes({ scope: 'single', code })
      if (res.success) {
        ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
        await fetchETFData()
      }
    })
    .catch(() => {})
}

const openEtfHistDeleteDialog = () => {
  etfHistDelVisible.value = true
}
const onEtfHistDelOpen = () => {
  etfHistDelScope.value = 'single'
  etfHistDelCode.value = ''
  etfHistDelRange.value = null
}
const submitEtfHistDelete = async () => {
  if (etfHistDelScope.value === 'single' && !etfHistDelCode.value.trim()) {
    ElMessage.warning('请填写 ETF 代码')
    return
  }
  const range = etfHistDelRange.value
  const startDate = range?.[0]
  const endDate = range?.[1]
  if (etfHistDelScope.value === 'all' && !startDate && !endDate) {
    try {
      await ElMessageBox.confirm(
        '将清空 ETF 历史行情表 fund_historical_quotes 的全部记录，是否继续？',
        '危险操作',
        { type: 'error', confirmButtonText: '仍要删除', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm('确定按上述条件删除 ETF 历史行情吗？此操作不可恢复。', '删除确认', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }
  etfHistDelLoading.value = true
  try {
    const res = await quotesService.deleteETFHistoricalQuotes({
      scope: etfHistDelScope.value,
      code: etfHistDelScope.value === 'single' ? etfHistDelCode.value.trim() : undefined,
      startDate,
      endDate
    })
    if (res.success) {
      ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
      etfHistDelVisible.value = false
      await fetchETFHistoricalData()
    } else {
      ElMessage.warning(res.message || '删除未完成')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '删除失败')
  } finally {
    etfHistDelLoading.value = false
  }
}
const confirmDeleteEtfHistoricalRow = (row: { code?: string; name?: string; date?: unknown }) => {
  const code = row?.code || ''
  const name = row?.name || ''
  const day = formatHistoricalRowDate(row?.date)
  if (!code || !day) {
    ElMessage.warning('当前行缺少代码或日期')
    return
  }
  ElMessageBox.confirm(`确定删除 ${code} ${name} 在 ${day} 的 ETF 历史记录吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
    .then(async () => {
      const res = await quotesService.deleteETFHistoricalQuotes({
        scope: 'single',
        code,
        startDate: day,
        endDate: day
      })
      if (res.success) {
        ElMessage.success(res.message || `已删除 ${res.data?.deleted ?? 0} 条`)
        await fetchETFHistoricalData()
      }
    })
    .catch(() => {})
}

const openTurnoverImportDialog = () => {
  turnoverImportDialogVisible.value = true
  turnoverImportResult.value = null
}

const onTurnoverImportFileChange = (uploadFile: any) => {
  turnoverImportFile.value = uploadFile.raw || null
}

const submitTurnoverImport = async () => {
  if (!turnoverImportFile.value) {
    ElMessage.warning('请先选择导入文件')
    return
  }
  turnoverImportLoading.value = true
  try {
    const res = await quotesService.importTurnoverRate(
      turnoverImportFile.value,
      turnoverImportTradeDate.value || undefined,
      turnoverImportDryRun.value,
      200
    )
    turnoverImportResult.value = res.data
    if (res.success) {
      ElMessage.success(turnoverImportDryRun.value ? 'Dry Run完成' : '导入完成，请手动点击“刷新”查看最新换手率')
    } else {
      ElMessage.warning('导入完成，但存在失败项')
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '换手率导入失败')
  } finally {
    turnoverImportLoading.value = false
  }
}

const downloadTurnoverTemplate = async (format: 'csv' | 'xlsx') => {
  try {
    const blob = await quotesService.downloadTurnoverTemplate(format)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `turnover_rate_import_template.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('模板下载失败')
  }
}

const openHistoricalTurnoverImportDialog = () => {
  historicalTurnoverImportDialogVisible.value = true
  historicalTurnoverImportResult.value = null
}

const onHistoricalTurnoverImportFileChange = (uploadFile: any) => {
  historicalTurnoverImportFile.value = uploadFile.raw || null
}

const submitHistoricalTurnoverImport = async () => {
  if (!historicalTurnoverImportFile.value) {
    ElMessage.warning('请先选择导入文件')
    return
  }
  historicalTurnoverImportLoading.value = true
  try {
    const res = await quotesService.importHistoricalTurnoverRate(
      historicalTurnoverImportFile.value,
      historicalTurnoverImportTradeDate.value || undefined,
      historicalTurnoverImportDryRun.value,
      200
    )
    historicalTurnoverImportResult.value = res.data
    if (res.success) {
      ElMessage.success(historicalTurnoverImportDryRun.value ? 'Dry Run完成' : '历史换手率更新完成，请手动点击“刷新”查看结果')
    } else {
      ElMessage.warning('更新完成，但存在失败项')
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '历史换手率更新失败')
  } finally {
    historicalTurnoverImportLoading.value = false
  }
}

// A股指数数据获取
const fetchIndexData = async () => {
  indexLoading.value = true
  const loadingInstance = showLoading()
  try {
    const response = await quotesService.getIndexQuotes({
      page: indexCurrentPage.value,
      pageSize: indexPageSize.value,
      keyword: indexSearchKeyword.value
    })
    
    if (response.success) {
      indexData.value = response.data
      indexTotal.value = response.total
    }
  } catch (error) {
    console.error('获取指数数据失败:', error)
    ElMessage.error('获取指数数据失败')
  } finally {
    indexLoading.value = false
    loadingInstance.close()
  }
}

const refreshIndexData = () => fetchIndexData()
const handleIndexSearch = () => {
  indexCurrentPage.value = 1
  fetchIndexData()
}
const handleIndexPageChange = () => fetchIndexData()
const handleIndexPageSizeChange = () => {
  indexCurrentPage.value = 1
  fetchIndexData()
}

// A股历史行情数据获取（日线走 /quotes/history 与 K 线等接口同源 ORM 序列化；多周期仍走 multi-period）
const fetchHistoricalData = async () => {
  historicalLoading.value = true
  const loadingInstance = showLoading()
  try {
    const response =
      historicalPeriod.value === 'daily'
        ? await quotesService.getHistoricalQuotes({
            page: historicalCurrentPage.value,
            pageSize: historicalPageSize.value,
            keyword: historicalSearchKeyword.value,
            startDate: historicalStartDate.value,
            endDate: historicalEndDate.value
          })
        : await quotesService.getMultiPeriodHistoricalQuotes({
            period: historicalPeriod.value,
            page: historicalCurrentPage.value,
            pageSize: historicalPageSize.value,
            keyword: historicalSearchKeyword.value,
            startDate: historicalStartDate.value,
            endDate: historicalEndDate.value
          })

    if (response.success) {
      historicalData.value = response.data
      historicalTotal.value = response.total
    }
  } catch (error) {
    console.error('获取历史行情数据失败:', error)
    ElMessage.error('获取历史行情数据失败')
  } finally {
    historicalLoading.value = false
    loadingInstance.close()
  }
}

const refreshHistoricalData = () => fetchHistoricalData()
const handleHistoricalSearch = () => {
  historicalCurrentPage.value = 1
  fetchHistoricalData()
}
const handleHistoricalPeriodChange = () => {
  historicalCurrentPage.value = 1
  fetchHistoricalData()
}
const handleHistoricalDateChange = () => {
  historicalCurrentPage.value = 1
  fetchHistoricalData()
}
const handleHistoricalPageChange = () => fetchHistoricalData()
const handleHistoricalPageSizeChange = () => {
  historicalCurrentPage.value = 1
  fetchHistoricalData()
}

// 导出历史数据
const openExportDialog = () => {
  exportForm.market = 'CN'
  exportForm.dateType = 'single'
  exportForm.date = ''
  exportForm.startDate = ''
  exportForm.endDate = ''
  exportForm.format = 'xlsx'
  if (exportFormRef.value) exportFormRef.value.resetFields()
  exportDialogVisible.value = true
}

const openHKExportDialog = () => {
  exportForm.market = 'HK'
  exportForm.dateType = 'single'
  exportForm.date = ''
  exportForm.startDate = ''
  exportForm.endDate = ''
  exportForm.format = 'xlsx'
  if (exportFormRef.value) exportFormRef.value.resetFields()
  exportDialogVisible.value = true
}

const submitExport = async () => {
  if (!exportFormRef.value) return
  await exportFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        exportLoading.value = true
        const params: any = { 
          format: exportForm.format,
          market: exportForm.market
        }
        if (exportForm.dateType === 'single') {
          params.date = exportForm.date
        } else {
          params.startDate = exportForm.startDate
          params.endDate = exportForm.endDate
        }
        
        const blob = await quotesService.exportHistoricalQuotes(params)
        
        // 创建下载链接
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        let filename = exportForm.market === 'CN' ? 'historical_quotes' : 'hk_historical_quotes'
        if (exportForm.dateType === 'single') {
          filename += `_${exportForm.date}`
        } else {
          filename += `_${exportForm.startDate}_to_${exportForm.endDate}`
        }
        filename += `.${exportForm.format}`
        
        link.setAttribute('download', filename)
        document.body.appendChild(link)
        link.click()
        link.parentNode?.removeChild(link)
        window.URL.revokeObjectURL(url)
        
        ElMessage.success('导出历史行情数据成功')
        exportDialogVisible.value = false
      } catch (error) {
        console.error('导出历史行情数据失败:', error)
        ElMessage.error('导出失败，请重试')
      } finally {
        exportLoading.value = false
      }
    }
  })
}

// A股行业板块数据获取
const fetchIndustryData = async () => {
  industryLoading.value = true
  const loadingInstance = showLoading()
  try {
    const response = await quotesService.getIndustryQuotes({
      page: industryCurrentPage.value,
      pageSize: industryPageSize.value,
      keyword: industrySearchKeyword.value
    })
    
    if (response.success) {
      industryData.value = response.data
      industryTotal.value = response.total
    }
  } catch (error) {
    console.error('获取行业板块数据失败:', error)
    ElMessage.error('获取行业板块数据失败')
  } finally {
    industryLoading.value = false
    loadingInstance.close()
  }
}

const refreshIndustryData = () => fetchIndustryData()
const handleIndustrySearch = () => {
  industryCurrentPage.value = 1
  fetchIndustryData()
}
const handleIndustryPageChange = () => fetchIndustryData()
const handleIndustryPageSizeChange = () => {
  industryCurrentPage.value = 1
  fetchIndustryData()
}

// 港股股票数据获取
const fetchHKStockData = async () => {
  hkStockLoading.value = true
  const loadingInstance = showLoading()
  try {
    const response = await quotesService.getHKStockQuotes({
      page: hkStockCurrentPage.value,
      pageSize: hkStockPageSize.value,
      keyword: hkStockSearchKeyword.value
    })
    
    if (response.success) {
      hkStockData.value = response.data
      hkStockTotal.value = response.total
    }
  } catch (error) {
    console.error('获取港股数据失败:', error)
    ElMessage.error('获取港股数据失败')
  } finally {
    hkStockLoading.value = false
    loadingInstance.close()
  }
}

const refreshHKStockData = () => fetchHKStockData()
const handleHKStockSearch = () => {
  hkStockCurrentPage.value = 1
  fetchHKStockData()
}
const handleHKStockPageChange = () => fetchHKStockData()
const handleHKStockPageSizeChange = () => {
  hkStockCurrentPage.value = 1
  fetchHKStockData()
}

// 港股历史行情数据获取
const fetchHKHistoricalData = async () => {
  hkHistoricalLoading.value = true
  const loadingInstance = showLoading()
  try {
    const response = await quotesService.getHKHistoricalQuotes({
      page: hkHistoricalCurrentPage.value,
      pageSize: hkHistoricalPageSize.value,
      keyword: hkHistoricalSearchKeyword.value,
      startDate: hkHistoricalStartDate.value,
      endDate: hkHistoricalEndDate.value
    })
    
    if (response.success) {
      hkHistoricalData.value = response.data
      hkHistoricalTotal.value = response.total
    }
  } catch (error) {
    console.error('获取港股历史行情数据失败:', error)
    ElMessage.error('获取港股历史行情数据失败')
  } finally {
    hkHistoricalLoading.value = false
    loadingInstance.close()
  }
}

const refreshHKHistoricalData = () => fetchHKHistoricalData()
const handleHKHistoricalSearch = () => {
  hkHistoricalCurrentPage.value = 1
  fetchHKHistoricalData()
}
const handleHKHistoricalDateChange = () => {
  hkHistoricalCurrentPage.value = 1
  fetchHKHistoricalData()
}
const handleHKHistoricalPageChange = () => fetchHKHistoricalData()
const handleHKHistoricalPageSizeChange = () => {
  hkHistoricalCurrentPage.value = 1
  fetchHKHistoricalData()
}

// 港股指数数据获取
const fetchHKIndexData = async () => {
  hkIndexLoading.value = true
  const loadingInstance = showLoading()
  try {
    const response = await quotesService.getHKIndexQuotes({
      page: hkIndexCurrentPage.value,
      pageSize: hkIndexPageSize.value,
      keyword: hkIndexSearchKeyword.value
    })
    
    if (response.success) {
      hkIndexData.value = response.data
      hkIndexTotal.value = response.total
    }
  } catch (error) {
    console.error('获取港股指数数据失败:', error)
    ElMessage.error('获取港股指数数据失败')
  } finally {
    hkIndexLoading.value = false
    loadingInstance.close()
  }
}

const refreshHKIndexData = () => fetchHKIndexData()
const handleHKIndexSearch = () => {
  hkIndexCurrentPage.value = 1
  fetchHKIndexData()
}
const handleHKIndexPageChange = () => fetchHKIndexData()
const handleHKIndexPageSizeChange = () => {
  hkIndexCurrentPage.value = 1
  fetchHKIndexData()
}

// 港股指数历史行情数据获取
const fetchHKIndexHistoricalData = async () => {
  hkIndexHistoricalLoading.value = true
  const loadingInstance = showLoading()
  try {
    const response = await quotesService.getHKIndexHistoricalQuotes({
      page: hkIndexHistoricalCurrentPage.value,
      pageSize: hkIndexHistoricalPageSize.value,
      keyword: hkIndexHistoricalSearchKeyword.value,
      startDate: hkIndexHistoricalStartDate.value,
      endDate: hkIndexHistoricalEndDate.value
    })
    
    if (response.success) {
      hkIndexHistoricalData.value = response.data
      hkIndexHistoricalTotal.value = response.total
    }
  } catch (error) {
    console.error('获取港股指数历史行情数据失败:', error)
    ElMessage.error('获取港股指数历史行情数据失败')
  } finally {
    hkIndexHistoricalLoading.value = false
    loadingInstance.close()
  }
}

const refreshHKIndexHistoricalData = () => fetchHKIndexHistoricalData()
const handleHKIndexHistoricalSearch = () => {
  hkIndexHistoricalCurrentPage.value = 1
  fetchHKIndexHistoricalData()
}
const handleHKIndexHistoricalDateChange = () => {
  hkIndexHistoricalCurrentPage.value = 1
  fetchHKIndexHistoricalData()
}
const handleHKIndexHistoricalPageChange = () => fetchHKIndexHistoricalData()
const handleHKIndexHistoricalPageSizeChange = () => {
  hkIndexHistoricalCurrentPage.value = 1
  fetchHKIndexHistoricalData()
}

// 初始化
onMounted(() => {
  fetchStockData()
})
</script>

<style scoped>
.quotes-view {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.tabs-section {
  margin-top: 20px;
}

.tab-content {
  padding: 20px 0;
}

.search-section {
  margin-bottom: 20px;
}

.pagination-section {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.responsive-table {
  font-size: 14px;
}

.price-up {
  color: #f56c6c;
}

.price-down {
  color: #67c23a;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-actions {
    margin-top: 10px;
    width: 100%;
  }

  .responsive-table {
    font-size: 12px;
  }
}
</style>