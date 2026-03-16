<template>
  <div class="datacollect-view">
    <!-- 当前任务状态 -->
    <div v-if="currentTask" class="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
      <div class="flex items-center">
        <el-icon class="text-yellow-600 mr-3"><Warning /></el-icon>
        <div>
          <h3 class="text-sm font-medium text-yellow-800">当前有任务正在运行</h3>
          <p class="text-sm text-yellow-700 mt-1">
            任务ID: {{ currentTask.task_id }} | 
            开始时间: {{ formatTime(currentTask.start_time) }}
          </p>
        </div>
      </div>
    </div>

    <!-- 标签页 -->
    <el-tabs v-model="activeMainTab" class="mb-8">
      <!-- A股历史数据采集 -->
      <el-tab-pane label="A股历史数据采集" name="ashare">
        <el-tabs v-model="activeAShareTab">
          <!-- AkShare标签页 -->
          <el-tab-pane label="历史数据采集-AkShare" name="akshare">
            <el-card>
              <div class="text-center mb-8">
                <el-icon class="text-6xl text-gray-400 mb-4"><DataAnalysis /></el-icon>
                <h2 class="text-2xl font-bold text-gray-900 mb-2">历史数据采集-AkShare</h2>
                <p class="text-gray-600">使用akshare采集A股历史行情数据（单任务执行，防重复采集）</p>
              </div>

              <!-- 采集配置表单 -->
              <div class="max-w-2xl mx-auto">
                <el-form @submit.prevent="startCollection" :model="form" label-width="120px">
                  <!-- 日期范围 -->
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="开始日期" required>
                        <el-date-picker
                          v-model="form.start_date"
                          type="date"
                          placeholder="选择开始日期"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="结束日期" required>
                        <el-date-picker
                          v-model="form.end_date"
                          type="date"
                          placeholder="选择结束日期"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- 股票选择 -->
                  <el-form-item label="股票选择">
                    <el-radio-group v-model="form.collection_type">
                      <el-radio value="single">单个股票采集</el-radio>
                      <el-radio value="multiple">多个股票采集</el-radio>
                      <el-radio value="all">全量股票采集</el-radio>
                    </el-radio-group>
                  </el-form-item>

                  <!-- 单个股票代码输入 -->
                  <el-form-item v-if="form.collection_type === 'single'" label="股票代码" required>
                    <el-input
                      v-model="form.single_stock_code"
                      placeholder="请输入股票代码，例如：000001"
                      clearable
                    />
                    <div class="text-sm text-gray-500 mt-1">支持输入单个股票代码进行采集</div>
                  </el-form-item>

                  <!-- 多个股票代码输入 -->
                  <el-form-item v-if="form.collection_type === 'multiple'" label="股票代码" required>
                    <el-input
                      v-model="form.stock_codes_text"
                      type="textarea"
                      :rows="5"
                      placeholder="请输入股票代码，每行一个，例如：&#10;000001&#10;000002&#10;000858"
                    />
                    <div class="text-sm text-gray-500 mt-1">支持输入多个股票代码，每行一个</div>
                  </el-form-item>

                  <!-- 全量采集说明 -->
                  <el-alert
                    v-if="form.collection_type === 'all'"
                    title="全量采集说明"
                    type="info"
                    :closable="false"
                    show-icon
                  >
                    <p>将采集数据库中所有股票的历史数据。由于akshare限流要求，系统采用单任务执行模式，
                    已采集过的股票数据将被跳过，避免重复采集。</p>
                  </el-alert>

                  <!-- 测试模式 -->
                  <el-form-item>
                    <el-checkbox v-model="form.test_mode">测试模式（只采集前5只股票）</el-checkbox>
                  </el-form-item>

                  <!-- 指标数据生成选项 -->
                  <el-form-item label="指标数据生成">
                    <div class="flex items-center mb-2">
                      <el-checkbox 
                        v-model="isAllSelected" 
                        :indeterminate="isIndeterminate"
                        @change="handleSelectAllIndicators"
                      >
                        全选
                      </el-checkbox>
                    </div>
                    <el-checkbox-group v-model="safeIndicators">
                      <el-checkbox value="ma">MA移动平均线</el-checkbox>
                      <el-checkbox value="mavol">MAVOL成交量移动平均线</el-checkbox>
                      <el-checkbox value="kdj">KDJ随机指标</el-checkbox>
                      <el-checkbox value="rsi">RSI相对强弱指标</el-checkbox>
                      <el-checkbox value="boll">BOLL布林带</el-checkbox>
                      <el-checkbox value="pvfrs">PVFRS指标</el-checkbox>
                    </el-checkbox-group>
                    <div class="text-sm text-gray-500 mt-1">选择需要同时生成的技术指标数据</div>
                  </el-form-item>

                  <!-- 操作按钮 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="loading"
                      :disabled="!!currentTask"
                      @click="startCollection"
                    >
                      <el-icon v-if="loading" class="mr-2"><Loading /></el-icon>
                      {{ loading ? '启动中...' : (currentTask ? '等待当前任务完成' : '开始采集') }}
                    </el-button>
                    <el-button @click="resetForm">重置</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-card>
          </el-tab-pane>

          <!-- TuShare标签页 -->
          <el-tab-pane label="历史数据采集-TuShare" name="tushare">
            <el-card>
              <div class="text-center mb-8">
                <el-icon class="text-6xl text-gray-400 mb-4"><DataAnalysis /></el-icon>
                <h2 class="text-2xl font-bold text-gray-900 mb-2">历史数据采集-TuShare</h2>
                <p class="text-gray-600">使用tushare采集A股全量历史行情数据</p>
              </div>

              <!-- TuShare采集配置表单 -->
              <div class="max-w-2xl mx-auto">
                <el-form @submit.prevent="startTushareCollection" :model="tushareForm" label-width="120px">
                  <!-- 日期范围 -->
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="开始日期" required>
                        <el-date-picker
                          v-model="tushareForm.start_date"
                          type="date"
                          placeholder="选择开始日期"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="结束日期" required>
                        <el-date-picker
                          v-model="tushareForm.end_date"
                          type="date"
                          placeholder="选择结束日期"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- 强制更新选项 -->
                  <el-form-item>
                    <el-checkbox v-model="tushareForm.force_update">
                      强制更新（如果已存在此日期的历史数据，将先删除后插入）
                    </el-checkbox>
                    <div class="text-sm text-gray-500 mt-1">
                      未选择强制更新时，如果已存在数据则跳过插入
                    </div>
                  </el-form-item>

                  <!-- 指标数据生成选项 -->
                  <el-form-item label="指标数据生成">
                    <div class="flex items-center mb-2">
                      <el-checkbox 
                        v-model="isAllTushareIndicatorsSelected" 
                        :indeterminate="isTushareIndicatorsIndeterminate"
                        @change="handleSelectAllTushareIndicators"
                      >
                        全选
                      </el-checkbox>
                    </div>
                    <el-checkbox-group v-model="safeTushareIndicators">
                      <el-checkbox value="ma">MA移动平均线</el-checkbox>
                      <el-checkbox value="mavol">MAVOL成交量移动平均线</el-checkbox>
                      <el-checkbox value="kdj">KDJ随机指标</el-checkbox>
                      <el-checkbox value="rsi">RSI相对强弱指标</el-checkbox>
                      <el-checkbox value="boll">BOLL布林带</el-checkbox>
                      <el-checkbox value="pvfrs">PVFRS指标</el-checkbox>
                    </el-checkbox-group>
                    <div class="text-sm text-gray-500 mt-1">选择需要同时生成的技术指标数据</div>
                  </el-form-item>

                  <!-- 操作按钮 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="tushareLoading"
                      :disabled="!!currentTask"
                      @click="startTushareCollection"
                    >
                      <el-icon v-if="tushareLoading" class="mr-2"><Loading /></el-icon>
                      {{ tushareLoading ? '启动中...' : (currentTask ? '等待当前任务完成' : '开始采集') }}
                    </el-button>
                    <el-button @click="resetTushareForm">重置</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-card>
          </el-tab-pane>

          <!-- 实时行情表标签页 -->
          <el-tab-pane label="历史数据采集-实时行情表" name="realtime_hist">
            <el-card>
              <div class="text-center mb-8">
                <el-icon class="text-6xl text-gray-400 mb-4"><DataAnalysis /></el-icon>
                <h2 class="text-2xl font-bold text-gray-900 mb-2">历史数据采集-实时行情表</h2>
                <p class="text-gray-600">根据日期区间，从 A 股实时行情表同步到历史行情表，并可同时生成技术指标</p>
              </div>

              <div class="max-w-2xl mx-auto">
                <el-form @submit.prevent="startRealtimeHistoricalCollection" :model="realtimeHistForm" label-width="120px">
                  <!-- 日期范围 -->
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="开始日期" required>
                        <el-date-picker
                          v-model="realtimeHistForm.start_date"
                          type="date"
                          placeholder="选择开始日期"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="结束日期" required>
                        <el-date-picker
                          v-model="realtimeHistForm.end_date"
                          type="date"
                          placeholder="选择结束日期"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- 指标数据生成选项 -->
                  <el-form-item label="指标数据生成">
                    <div class="flex items-center mb-2">
                      <el-checkbox 
                        v-model="isAllRealtimeIndicatorsSelected" 
                        :indeterminate="isRealtimeIndicatorsIndeterminate"
                        @change="handleSelectAllRealtimeIndicators"
                      >
                        全选
                      </el-checkbox>
                    </div>
                    <el-checkbox-group v-model="safeRealtimeIndicators">
                      <el-checkbox value="ma">MA移动平均线</el-checkbox>
                      <el-checkbox value="mavol">MAVOL成交量移动平均线</el-checkbox>
                      <el-checkbox value="kdj">KDJ随机指标</el-checkbox>
                      <el-checkbox value="rsi">RSI相对强弱指标</el-checkbox>
                      <el-checkbox value="boll">BOLL布林带</el-checkbox>
                      <el-checkbox value="pvfrs">PVFRS指标</el-checkbox>
                    </el-checkbox-group>
                    <div class="text-sm text-gray-500 mt-1">选择需要同时生成的技术指标数据</div>
                  </el-form-item>

                  <!-- 操作按钮 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="loading"
                      :disabled="!!currentTask"
                      @click="startRealtimeHistoricalCollection"
                    >
                      <el-icon v-if="loading" class="mr-2"><Loading /></el-icon>
                      {{ loading ? '启动中...' : (currentTask ? '等待当前任务完成' : '开始采集') }}
                    </el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>

      <!-- A股实时数据采集 -->
      <el-tab-pane label="A股实时数据采集" name="ashare_realtime">
        <el-card>
          <div class="text-center mb-8">
            <el-icon class="text-6xl text-gray-400 mb-4"><DataAnalysis /></el-icon>
            <h2 class="text-2xl font-bold text-gray-900 mb-2">A股实时数据采集</h2>
            <p class="text-gray-600">采集并更新A股实时行情数据（写入 stock_realtime_quote）</p>
          </div>

          <div class="max-w-2xl mx-auto">
            <el-form :key="'ashare-realtime-form'" @submit.prevent="startAShareRealtimeCollection" :model="ashareRealtimeForm" label-width="120px">
              <el-form-item label="股票选择">
                <el-radio-group v-model="ashareRealtimeForm.collection_type">
                  <el-radio value="single">单个股票采集</el-radio>
                  <el-radio value="all">全量股票采集</el-radio>
                </el-radio-group>
              </el-form-item>

              <el-form-item v-if="ashareRealtimeForm.collection_type === 'single'" label="股票代码" required>
                <el-input
                  v-model="ashareRealtimeForm.stock_code"
                  placeholder="请输入股票代码，例如：000001"
                  clearable
                />
              </el-form-item>

              <el-alert
                v-if="ashareRealtimeForm.collection_type === 'all'"
                title="全量采集说明"
                type="info"
                :closable="false"
                show-icon
                class="mb-4"
              >
                <p>将采集并更新全部A股实时行情数据。</p>
              </el-alert>

              <el-form-item>
                <el-button
                  type="primary"
                  :loading="ashareRealtimeLoading"
                  :disabled="!!currentTask"
                  @click="startAShareRealtimeCollection"
                >
                  <el-icon v-if="ashareRealtimeLoading" class="mr-2"><Loading /></el-icon>
                  {{ ashareRealtimeLoading ? '启动中...' : (currentTask ? '等待当前任务完成' : '开始采集') }}
                </el-button>
                <el-button @click="resetAShareRealtimeForm">重置</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 港股历史数据采集 -->
      <el-tab-pane label="港股历史数据采集" name="hkshare">
        <el-tabs v-model="activeHKShareTab">
          <el-tab-pane label="港股历史数据采集-AkShare" name="hk_akshare">
            <el-card>
              <div class="text-center mb-8">
                <el-icon class="text-6xl text-gray-400 mb-4"><DataAnalysis /></el-icon>
                <h2 class="text-2xl font-bold text-gray-900 mb-2">港股历史数据采集-AkShare</h2>
                <p class="text-gray-600">使用akshare采集港股历史行情数据</p>
              </div>

              <div class="max-w-2xl mx-auto">
                <el-form @submit.prevent="startHKCollection" :model="hkForm" label-width="120px">
                  <!-- 日期范围 -->
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="开始日期" required>
                        <el-date-picker
                          v-model="hkForm.start_date"
                          type="date"
                          placeholder="选择开始日期"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="结束日期" required>
                        <el-date-picker
                          v-model="hkForm.end_date"
                          type="date"
                          placeholder="选择结束日期"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- 采集类型 -->
                  <el-form-item label="采集类型" required>
                    <el-radio-group v-model="hkForm.collection_type">
                      <el-radio label="specified">指定股票</el-radio>
                      <el-radio label="all">全量采集</el-radio>
                      <el-radio label="sync_realtime">从实时行情表采集</el-radio>
                    </el-radio-group>
                  </el-form-item>

                  <!-- 港股代码 -->
                  <el-form-item label="港股代码" required v-if="hkForm.collection_type === 'specified'">
                    <el-input
                      v-model="hkForm.stock_codes_text"
                      type="textarea"
                      :rows="5"
                      placeholder="请输入港股代码（5位数字），每行一个，例如：&#10;00700&#10;09988"
                    />
                    <div class="text-sm text-gray-500 mt-1">请输入需要采集的港股代码</div>
                  </el-form-item>

                  <!-- 全量采集说明 -->
                  <el-alert
                    v-if="hkForm.collection_type === 'all'"
                    title="全量采集说明"
                    type="info"
                    :closable="false"
                    show-icon
                    class="mb-4"
                  >
                    <p>将采集数据库中所有港股的历史数据。由于akshare限流要求，系统采用单任务执行模式，每次采集间隔5秒。</p>
                  </el-alert>

                  <!-- 从实时行情同步说明 -->
                  <el-alert
                    v-if="hkForm.collection_type === 'sync_realtime'"
                    title="实时同步说明"
                    type="success"
                    :closable="false"
                    show-icon
                    class="mb-4"
                  >
                    <p>将从 [stock_realtime_quote_hk] 实时行情表中读取指定日期范围内的数据并同步到历史行情表，同时会为自选股自动计算各项指标。</p>
                  </el-alert>

                  <!-- 强制更新选项 -->
                  <el-form-item>
                    <el-checkbox v-model="hkForm.force_update">
                      强制更新（如果已存在此日期的历史数据，将重新采集并更新）
                    </el-checkbox>
                    <div class="text-sm text-gray-500 mt-1">
                      未选择强制更新时，如果已存在数据则跳过插入
                    </div>
                  </el-form-item>

                  <!-- 操作按钮 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="hkLoading"
                      :disabled="!!currentTask"
                      @click="startHKCollection"
                    >
                      <el-icon v-if="hkLoading" class="mr-2"><Loading /></el-icon>
                      {{ hkLoading ? '启动中...' : (currentTask ? '等待当前任务完成' : '开始采集') }}
                    </el-button>
                    <el-button @click="resetHKForm">重置</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>

      <!-- 港股实时数据采集 -->
      <el-tab-pane label="港股实时数据采集" name="hkshare_realtime">
        <el-card>
          <div class="text-center mb-8">
            <el-icon class="text-6xl text-gray-400 mb-4"><DataAnalysis /></el-icon>
            <h2 class="text-2xl font-bold text-gray-900 mb-2">港股实时数据采集</h2>
            <p class="text-gray-600">采集并更新港股实时行情数据（写入 stock_realtime_quote_hk）</p>
          </div>

          <div class="max-w-2xl mx-auto">
            <el-form :key="'hk-realtime-form'" @submit.prevent="startHKRealtimeCollection" :model="hkRealtimeForm" label-width="120px">
              <el-form-item label="股票选择">
                <el-radio-group v-model="hkRealtimeForm.collection_type">
                  <el-radio value="single">单个股票采集</el-radio>
                  <el-radio value="all">全量股票采集</el-radio>
                </el-radio-group>
              </el-form-item>

              <el-form-item v-if="hkRealtimeForm.collection_type === 'single'" label="港股代码" required>
                <el-input
                  v-model="hkRealtimeForm.stock_code"
                  placeholder="请输入港股代码（5位数字），例如：00700"
                  clearable
                />
              </el-form-item>

              <el-alert
                v-if="hkRealtimeForm.collection_type === 'all'"
                title="全量采集说明"
                type="info"
                :closable="false"
                show-icon
                class="mb-4"
              >
                <p>将采集并更新全部港股实时行情数据。</p>
              </el-alert>

              <el-form-item>
                <el-button
                  type="primary"
                  :loading="hkRealtimeLoading"
                  :disabled="!!currentTask"
                  @click="startHKRealtimeCollection"
                >
                  <el-icon v-if="hkRealtimeLoading" class="mr-2"><Loading /></el-icon>
                  {{ hkRealtimeLoading ? '启动中...' : (currentTask ? '等待当前任务完成' : '开始采集') }}
                </el-button>
                <el-button @click="resetHKRealtimeForm">重置</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 任务列表 -->
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span>采集任务</span>
          <el-button type="text" @click="loadTasks" :icon="Refresh">
            刷新
          </el-button>
        </div>
      </template>

      <div v-if="tasks.length === 0" class="text-center text-gray-500 py-8">
        暂无采集任务
      </div>
      <div v-else class="space-y-4">
        <el-card
          v-for="task in tasks"
          :key="task.task_id"
          shadow="hover"
          class="mb-4"
        >
          <div class="flex justify-between items-start mb-3">
            <div>
              <h4 class="font-medium text-gray-900">任务 {{ task.task_id }}</h4>
              <p class="text-sm text-gray-500">
                {{ formatTime(task.start_time) }} - {{ task.end_time ? formatTime(task.end_time) : '进行中' }}
              </p>
            </div>
            <div class="flex items-center space-x-2">
              <el-tag
                :type="getStatusType(task.status)"
                size="small"
              >
                {{ getStatusText(task.status) }}
              </el-tag>
              <el-button
                v-if="task.status === 'running'"
                type="danger"
                size="small"
                @click="cancelTask(task.task_id)"
              >
                取消
              </el-button>
            </div>
          </div>
          
          <!-- 进度条 -->
          <div v-if="task.status === 'running'" class="mb-3">
            <div class="flex justify-between text-sm text-gray-600 mb-1">
              <span>进度</span>
              <span>{{ task.progress }}%</span>
            </div>
            <el-progress :percentage="task.progress" />
          </div>

          <!-- 统计信息 -->
          <el-row :gutter="20" class="text-sm">
            <el-col :span="6">
              <span class="text-gray-500">总股票数:</span>
              <span class="font-medium">{{ task.total_stocks }}</span>
            </el-col>
            <el-col :span="6">
              <span class="text-gray-500">成功:</span>
              <span class="font-medium text-green-600">{{ task.success_count }}</span>
            </el-col>
            <el-col :span="6">
              <span class="text-gray-500">失败:</span>
              <span class="font-medium text-red-600">{{ task.failed_count }}</span>
            </el-col>
            <el-col :span="6">
              <span class="text-gray-500">新增数据:</span>
              <span class="font-medium text-blue-600">{{ task.collected_count }}</span>
            </el-col>
          </el-row>

          <!-- 错误信息 -->
          <el-alert
            v-if="task.error_message"
            :title="task.error_message"
            type="error"
            :closable="false"
            show-icon
            class="mt-3"
          />
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { 
  ElMessage, 
  ElMessageBox,
  ElRadioGroup,
  ElRadio,
  ElCheckbox,
  ElProgress,
  ElTabs,
  ElTabPane
} from 'element-plus'
import { 
  DataAnalysis, 
  Warning, 
  Loading, 
  Refresh
} from '@element-plus/icons-vue'
import axios from 'axios'
import { API_BASE } from '@/config/api'

// 类型定义
interface Task {
  task_id: string
  status: string
  progress: number
  total_stocks: number
  processed_stocks: number
  success_count: number
  failed_count: number
  collected_count: number
  skipped_count: number
  start_time: string
  end_time?: string
  error_message?: string
  failed_details: string[]
}

interface CurrentTask {
  task_id: string
  status: string
  start_time: string
}

interface FormData {
  start_date: string
  end_date: string
  collection_type: 'single' | 'multiple' | 'all'
  single_stock_code: string
  stock_codes_text: string
  test_mode: boolean
  indicators: string[]
}

interface HKFormData {
  start_date: string
  end_date: string
  stock_codes_text: string
  collection_type: 'specified' | 'all' | 'sync_realtime'
  force_update: boolean
}

interface RealtimeFormData {
  collection_type: 'single' | 'all'
  stock_code: string
}

interface RequestData {
  start_date: string
  end_date: string
  test_mode: boolean
  stock_codes?: string[]
  full_collection_mode?: boolean
  market?: string
  force_update?: boolean
  indicators?: string[]
  sync_from_realtime?: boolean
}

interface RealtimeHistRequest {
  start_date: string
  end_date: string
  indicators?: string[]
}

// 标签页状态
const activeMainTab = ref('ashare')
const activeAShareTab = ref('akshare')
const activeHKShareTab = ref('hk_akshare')

// 表单数据
const form = ref<FormData>({
  start_date: '',
  end_date: '',
  collection_type: 'single',
  single_stock_code: '',
  stock_codes_text: '',
  test_mode: false,
  indicators: [] as string[]  // 明确类型，确保始终是数组
})

// HK表单数据
const hkForm = ref<HKFormData>({
  start_date: '',
  end_date: '',
  stock_codes_text: '',
  collection_type: 'specified',
  force_update: false
})

// 实时采集表单
const ashareRealtimeForm = ref<RealtimeFormData>({
  collection_type: 'single',
  stock_code: ''
})

const hkRealtimeForm = ref<RealtimeFormData>({
  collection_type: 'single',
  stock_code: ''
})

// TuShare表单数据
interface TushareFormData {
  start_date: string
  end_date: string
  force_update: boolean
  indicators: string[]
}

const tushareForm = ref<TushareFormData>({
  start_date: '',
  end_date: '',
  force_update: false,
  indicators: []
})

// 实时行情表历史采集表单
interface RealtimeHistFormData {
  start_date: string
  end_date: string
  indicators: string[]
}

const realtimeHistForm = ref<RealtimeHistFormData>({
  start_date: '',
  end_date: '',
  indicators: []
})

// 状态数据
const tasks = ref<Task[]>([])
const currentTask = ref<CurrentTask | null>(null)
const loading = ref(false)
const hkLoading = ref(false)
const tushareLoading = ref(false)
const ashareRealtimeLoading = ref(false)
const hkRealtimeLoading = ref(false)
const pollingInterval = ref<NodeJS.Timeout | null>(null)

// 计算属性
const allIndicators = ['ma', 'mavol', 'kdj', 'rsi', 'boll', 'pvfrs']

// 确保 indicators 始终是数组的计算属性
const safeIndicators = computed({
  get: () => {
    const indicators = form.value.indicators
    return Array.isArray(indicators) ? indicators : []
  },
  set: (val) => {
    form.value.indicators = Array.isArray(val) ? val : []
  }
})

const isIndeterminate = computed(() => {
  const indicators = safeIndicators.value
  const selectedCount = indicators.length
  if (selectedCount === 0) {
    return false
  } else if (selectedCount === allIndicators.length) {
    return false
  } else {
    return true
  }
})

const isAllSelected = computed(() => {
  return safeIndicators.value.length === allIndicators.length
})

const handleSelectAllIndicators = (checked: boolean | string | number | boolean[] | undefined) => {
  const isChecked = typeof checked === 'boolean' ? checked : Boolean(checked)
  if (isChecked) {
    safeIndicators.value = [...allIndicators]
  } else {
    safeIndicators.value = []
  }
}

// TuShare 指标选择
const safeTushareIndicators = computed({
  get: () => {
    const indicators = tushareForm.value.indicators
    return Array.isArray(indicators) ? indicators : []
  },
  set: (val) => {
    tushareForm.value.indicators = Array.isArray(val) ? val : []
  }
})

const isTushareIndicatorsIndeterminate = computed(() => {
  const indicators = safeTushareIndicators.value
  const selectedCount = indicators.length
  if (selectedCount === 0) return false
  if (selectedCount === allIndicators.length) return false
  return true
})

const isAllTushareIndicatorsSelected = computed(() => {
  return safeTushareIndicators.value.length === allIndicators.length
})

const handleSelectAllTushareIndicators = (checked: boolean | string | number | boolean[] | undefined) => {
  const isChecked = typeof checked === 'boolean' ? checked : Boolean(checked)
  if (isChecked) {
    safeTushareIndicators.value = [...allIndicators]
  } else {
    safeTushareIndicators.value = []
  }
}

// 实时行情表指标选择
const safeRealtimeIndicators = computed<string[]>({
  get: () => {
    const indicators = realtimeHistForm.value.indicators
    return Array.isArray(indicators) ? indicators : []
  },
  set: (val: string[]) => {
    realtimeHistForm.value.indicators = Array.isArray(val) ? val : []
  }
})

const isRealtimeIndicatorsIndeterminate = computed(() => {
  const indicators = safeRealtimeIndicators.value
  const selectedCount = indicators.length
  if (selectedCount === 0) {
    return false
  } else if (selectedCount === allIndicators.length) {
    return false
  } else {
    return true
  }
})

const isAllRealtimeIndicatorsSelected = computed(() => {
  return safeRealtimeIndicators.value.length === allIndicators.length
})

const handleSelectAllRealtimeIndicators = (checked: boolean | string | number | boolean[] | undefined) => {
  const isChecked = typeof checked === 'boolean' ? checked : Boolean(checked)
  if (isChecked) {
    safeRealtimeIndicators.value = [...allIndicators]
  } else {
    safeRealtimeIndicators.value = []
  }
}

// 方法
const startCollection = async () => {
  try {
    loading.value = true
    
    // 验证表单
    if (!form.value.start_date || !form.value.end_date) {
      ElMessage.error('请选择开始日期和结束日期')
      return
    }
    
    // 检查当前任务状态
    if (currentTask.value) {
      ElMessage.error('已有采集任务正在运行，请等待完成后再启动新任务')
      return
    }
    
    // 准备请求数据
    const requestData: RequestData = {
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      test_mode: form.value.test_mode,
      indicators: safeIndicators.value  // 使用安全的数组值
    }

    // 根据采集类型设置股票代码
    if (form.value.collection_type === 'single') {
      if (!form.value.single_stock_code.trim()) {
        ElMessage.error('请输入股票代码')
        return
      }
      requestData.stock_codes = [form.value.single_stock_code.trim()]
    } else if (form.value.collection_type === 'multiple') {
      const stockCodes = form.value.stock_codes_text
        .split('\n')
        .map(code => code.trim())
        .filter(code => code.length > 0)
      
      if (stockCodes.length === 0) {
        ElMessage.error('请输入至少一个股票代码')
        return
      }
      
      requestData.stock_codes = stockCodes
    } else if (form.value.collection_type === 'all') {
      // 全量采集模式
      requestData.full_collection_mode = true
    }

    console.log('发送请求:', requestData)
    const response = await axios.post(`${API_BASE}/api/data-collection/historical`, requestData)
    
    if (response.data.status === 'started') {
      ElMessage.success('采集任务已启动')
      loadTasks()
      loadCurrentTask()
    }
    
  } catch (error: any) {
    console.error('启动采集任务失败:', error)
    let errorMsg = '启动采集任务失败'
    
    if (error.response) {
      // 服务器响应了错误状态码
      errorMsg = error.response.data?.detail || `服务器错误 (${error.response.status})`
    } else if (error.request) {
      // 请求已发出但没有收到响应
      errorMsg = '无法连接到服务器，请检查网络连接'
    } else {
      // 其他错误
      errorMsg = error.message || '未知错误'
    }
    
    ElMessage.error(errorMsg)
  } finally {
    loading.value = false
  }
}

// 从实时行情表同步历史数据（A股）
const startRealtimeHistoricalCollection = async () => {
  try {
    loading.value = true

    if (!realtimeHistForm.value.start_date || !realtimeHistForm.value.end_date) {
      ElMessage.error('请选择开始日期和结束日期')
      return
    }

    if (currentTask.value) {
      ElMessage.error('已有采集任务正在运行，请等待完成后再启动新任务')
      return
    }

    const payload: RealtimeHistRequest = {
      start_date: realtimeHistForm.value.start_date,
      end_date: realtimeHistForm.value.end_date,
      indicators: safeRealtimeIndicators.value
    }

    console.log('发送实时行情表历史采集请求:', payload)
    const response = await axios.post(`${API_BASE}/api/data-collection/realtime-historical`, payload)

    if (response.data.status === 'started') {
      ElMessage.success('实时行情表历史采集任务已启动')
      loadTasks()
      loadCurrentTask()
    }
  } catch (error: any) {
    console.error('启动实时行情表历史采集任务失败:', error)
    let errorMsg = '启动实时行情表历史采集任务失败'

    if (error.response) {
      errorMsg = error.response.data?.detail || `服务器错误 (${error.response.status})`
    } else if (error.request) {
      errorMsg = '无法连接到服务器，请检查网络连接'
    } else {
      errorMsg = error.message || '未知错误'
    }

    ElMessage.error(errorMsg)
  } finally {
    loading.value = false
  }
}

const startHKCollection = async () => {
  try {
    hkLoading.value = true
    
    // 验证表单
    if (!hkForm.value.start_date || !hkForm.value.end_date) {
      ElMessage.error('请选择开始日期和结束日期')
      return
    }

    if (hkForm.value.collection_type === 'specified' && !hkForm.value.stock_codes_text.trim()) {
      ElMessage.error('请输入港股代码')
      return
    }
    
    // 检查当前任务状态
    if (currentTask.value) {
      ElMessage.error('已有采集任务正在运行，请等待完成后再启动新任务')
      return
    }
    
    // 准备请求数据
    const requestData: RequestData = {
      start_date: hkForm.value.start_date,
      end_date: hkForm.value.end_date,
      test_mode: false,
      market: 'HK',
      force_update: hkForm.value.force_update
    }

    if (hkForm.value.collection_type === 'specified') {
      const stockCodes = hkForm.value.stock_codes_text
        .split('\n')
        .map(code => code.trim())
        .filter(code => code.length > 0)
      requestData.stock_codes = stockCodes
    } else if (hkForm.value.collection_type === 'all') {
      requestData.full_collection_mode = true
    } else if (hkForm.value.collection_type === 'sync_realtime') {
      requestData.sync_from_realtime = true
    }

    console.log('发送港股采集请求:', requestData)
    const response = await axios.post(`${API_BASE}/api/data-collection/historical`, requestData)
    
    if (response.data.status === 'started') {
      ElMessage.success('港股采集任务已启动')
      loadTasks()
      loadCurrentTask()
    }
    
  } catch (error: any) {
    console.error('启动港股采集任务失败:', error)
    let errorMsg = '启动港股采集任务失败'
    
    if (error.response) {
      errorMsg = error.response.data?.detail || `服务器错误 (${error.response.status})`
    } else if (error.request) {
      errorMsg = '无法连接到服务器，请检查网络连接'
    } else {
      errorMsg = error.message || '未知错误'
    }
    
    ElMessage.error(errorMsg)
  } finally {
    hkLoading.value = false
  }
}

const loadTasks = async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/data-collection/tasks`)
    // 确保 tasks.value 始终是数组
    const data = response.data
    if (Array.isArray(data)) {
      tasks.value = data
    } else if (data && Array.isArray(data.tasks)) {
      tasks.value = data.tasks
    } else if (data && Array.isArray(data.data)) {
      tasks.value = data.data
    } else {
      // 如果数据格式不符合预期，设置为空数组
      console.warn('任务列表数据格式不符合预期:', data)
      tasks.value = []
    }
  } catch (error) {
    console.error('加载任务列表失败:', error)
    // 发生错误时确保 tasks 是空数组
    tasks.value = []
  }
}

const loadCurrentTask = async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/data-collection/current-task`)
    currentTask.value = response.data.current_task
  } catch (error) {
    console.error('加载当前任务信息失败:', error)
  }
}

const cancelTask = async (taskId: string) => {
  try {
    await ElMessageBox.confirm('确定要取消这个任务吗？', '确认取消', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await axios.delete(`${API_BASE}/api/data-collection/tasks/${taskId}`)
    ElMessage.success('任务已取消')
    loadTasks()
    loadCurrentTask()
    
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('取消任务失败:', error)
      ElMessage.error(error.response?.data?.detail || '取消任务失败')
    }
  }
}

const resetForm = () => {
  form.value = {
    start_date: '',
    end_date: '',
    collection_type: 'single',
    single_stock_code: '',
    stock_codes_text: '',
    test_mode: false,
    indicators: [] as string[]  // 确保始终是数组
  }
  // 额外检查，确保 indicators 是数组
  if (!Array.isArray(form.value.indicators)) {
    form.value.indicators = []
  }
}

const resetHKForm = () => {
  hkForm.value = {
    start_date: '',
    end_date: '',
    stock_codes_text: '',
    collection_type: 'specified',
    force_update: false
  }
}

const resetAShareRealtimeForm = () => {
  ashareRealtimeForm.value = {
    collection_type: 'single',
    stock_code: ''
  }
}

const resetHKRealtimeForm = () => {
  hkRealtimeForm.value = {
    collection_type: 'single',
    stock_code: ''
  }
}

const resetTushareForm = () => {
  tushareForm.value = {
    start_date: '',
    end_date: '',
    force_update: false,
    indicators: []
  }
}

const startTushareCollection = async () => {
  try {
    tushareLoading.value = true
    
    // 验证表单
    if (!tushareForm.value.start_date || !tushareForm.value.end_date) {
      ElMessage.error('请选择开始日期和结束日期')
      return
    }
    
    // 检查当前任务状态
    if (currentTask.value) {
      ElMessage.error('已有采集任务正在运行，请等待完成后再启动新任务')
      return
    }

    // 使用TuShare采集全量历史数据时，强制附加 MA、MAVOL、PVFRS 指标
    const indicatorsToRun = Array.from(
      new Set([...safeTushareIndicators.value, 'ma', 'mavol', 'pvfrs'])
    )

    console.log('发送TuShare采集请求:', tushareForm.value)
    const response = await axios.post(`${API_BASE}/api/data-collection/tushare-historical`, {
      start_date: tushareForm.value.start_date,
      end_date: tushareForm.value.end_date,
      force_update: tushareForm.value.force_update,
      indicators: indicatorsToRun
    })
    
    if (response.data.status === 'started') {
      ElMessage.success('TuShare采集任务已启动')
      loadTasks()
      loadCurrentTask()
    }
    
  } catch (error: any) {
    console.error('启动TuShare采集任务失败:', error)
    let errorMsg = '启动TuShare采集任务失败'
    
    if (error.response) {
      errorMsg = error.response.data?.detail || `服务器错误 (${error.response.status})`
    } else if (error.request) {
      errorMsg = '无法连接到服务器，请检查网络连接'
    } else {
      errorMsg = error.message || '未知错误'
    }
    
    ElMessage.error(errorMsg)
  } finally {
    tushareLoading.value = false
  }
}

const startAShareRealtimeCollection = async () => {
  try {
    ashareRealtimeLoading.value = true
    if (ashareRealtimeForm.value.collection_type === 'single' && !ashareRealtimeForm.value.stock_code) {
      ElMessage.error('请输入股票代码')
      return
    }

    const payload = {
      market: 'CN',
      stock_codes: ashareRealtimeForm.value.collection_type === 'single' ? [ashareRealtimeForm.value.stock_code] : [],
      full_collection_mode: ashareRealtimeForm.value.collection_type === 'all'
    }

    const response = await axios.post(`${API_BASE}/api/data-collection/realtime`, payload)
    if (response.data.status === 'started') {
      ElMessage.success('A股实时采集任务已启动')
      loadTasks()
      loadCurrentTask()
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '启动失败')
  } finally {
    ashareRealtimeLoading.value = false
  }
}

const startHKRealtimeCollection = async () => {
  try {
    hkRealtimeLoading.value = true
    if (hkRealtimeForm.value.collection_type === 'single' && !hkRealtimeForm.value.stock_code) {
      ElMessage.error('请输入港股代码')
      return
    }

    const payload = {
      market: 'HK',
      stock_codes: hkRealtimeForm.value.collection_type === 'single' ? [hkRealtimeForm.value.stock_code] : [],
      full_collection_mode: hkRealtimeForm.value.collection_type === 'all'
    }

    const response = await axios.post(`${API_BASE}/api/data-collection/realtime`, payload)
    if (response.data.status === 'started') {
      ElMessage.success('港股实时采集任务已启动')
      loadTasks()
      loadCurrentTask()
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '启动失败')
  } finally {
    hkRealtimeLoading.value = false
  }
}

const getStatusText = (status: string): string => {
  const statusMap: Record<string, string> = {
    'running': '运行中',
    'completed': '已完成',
    'failed': '失败',
    'cancelled': '已取消'
  }
  return statusMap[status] || status
}

const getStatusType = (status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const typeMap: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    'running': 'primary',
    'completed': 'success',
    'failed': 'danger',
    'cancelled': 'warning'
  }
  return typeMap[status] || 'info'
}

const formatTime = (timeStr: string): string => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}

const startPolling = () => {
  pollingInterval.value = setInterval(() => {
    loadTasks()
    loadCurrentTask()
  }, 5000) // 每5秒刷新一次
}

const stopPolling = () => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
}

// 生命周期
onMounted(() => {
  loadTasks()
  loadCurrentTask()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.datacollect-view {
  padding: 20px;
}
</style>