<template>
  <div class="datacollect-view">
    <!-- 当前任务状态（仅运行中显示；完成后依赖轮询清空，避免仍显示「等待任务完成」） -->
    <div v-if="currentTaskIsRunning && currentTask" class="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
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
                      <el-checkbox value="icost">无穷成本均线</el-checkbox>
                    </el-checkbox-group>
                    <div class="text-sm text-gray-500 mt-1">选择需要同时生成的技术指标数据</div>
                  </el-form-item>

                  <!-- 操作按钮 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="loading"
                      :disabled="currentTaskIsRunning"
                      @click="startCollection"
                    >
                      <el-icon v-if="loading" class="mr-2"><Loading /></el-icon>
                      {{ loading ? '启动中...' : (currentTaskIsRunning ? '等待当前任务完成' : '开始采集') }}
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
                      <el-checkbox value="icost">无穷成本均线</el-checkbox>
                    </el-checkbox-group>
                    <div class="text-sm text-gray-500 mt-1">选择需要同时生成的技术指标数据</div>
                  </el-form-item>

                  <!-- 操作按钮 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="tushareLoading"
                      :disabled="currentTaskIsRunning"
                      @click="startTushareCollection"
                    >
                      <el-icon v-if="tushareLoading" class="mr-2"><Loading /></el-icon>
                      {{ tushareLoading ? '启动中...' : (currentTaskIsRunning ? '等待当前任务完成' : '开始采集') }}
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
                      <el-checkbox value="icost">无穷成本均线</el-checkbox>
                    </el-checkbox-group>
                    <div class="text-sm text-gray-500 mt-1">选择需要同时生成的技术指标数据</div>
                  </el-form-item>

                  <!-- 操作按钮 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="loading"
                      :disabled="currentTaskIsRunning"
                      @click="startRealtimeHistoricalCollection"
                    >
                      <el-icon v-if="loading" class="mr-2"><Loading /></el-icon>
                      {{ loading ? '启动中...' : (currentTaskIsRunning ? '等待当前任务完成' : '开始采集') }}
                    </el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-card>
          </el-tab-pane>

          <!-- 历史数据采集-文件标签页 -->
          <el-tab-pane label="历史数据采集-文件" name="file">
            <el-card>
              <div class="text-center mb-8">
                <el-icon class="text-6xl text-gray-400 mb-4"><DataAnalysis /></el-icon>
                <h2 class="text-2xl font-bold text-gray-900 mb-2">历史数据采集-文件</h2>
                <p class="text-gray-600">从本地文件（TXT/CSV）采集A股历史行情数据并入库</p>
              </div>

              <!-- 文件采集配置表单 -->
              <div class="max-w-2xl mx-auto">
                <el-form @submit.prevent="startFileCollection" :model="fileForm" label-width="120px">
                  <!-- 日期范围 -->
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="开始日期" required>
                        <el-date-picker
                          v-model="fileForm.start_date"
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
                          v-model="fileForm.end_date"
                          type="date"
                          placeholder="选择结束日期"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- 文件类型选择 -->
                  <el-form-item label="文件类型" required>
                    <el-radio-group v-model="fileForm.file_type">
                      <el-radio label="txt">TXT (SQL脚本)</el-radio>
                      <el-radio label="csv">CSV (通用格式)</el-radio>
                      <el-radio label="xlsx">XLSX (Excel格式)</el-radio>
                    </el-radio-group>
                    <div class="text-sm text-gray-500 mt-1">
                      TXT 格式应包含 SQL INSERT/REPLACE 语句；CSV/XLSX 格式应包含代码和行情字段
                    </div>
                  </el-form-item>

                  <!-- 文件上传 -->
                  <el-form-item label="上传文件" required>
                    <el-upload
                      class="upload-demo"
                      :action="`${API_BASE}/api/data-collection/upload-historical-file`"
                      :on-success="handleFileUploadSuccess"
                      :on-error="handleFileUploadError"
                      :before-upload="beforeFileUpload"
                      multiple
                      drag
                    >
                      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                      <div class="el-upload__text">
                        将文件拖到此处，或<em>点击上传</em>
                      </div>
                      <template #tip>
                        <div class="el-upload__tip">
                          请上传 daily_YYYYMMDD.txt、.csv 或 .xlsx 格式的文件
                        </div>
                      </template>
                    </el-upload>
                  </el-form-item>

                  <!-- 强制更新选项 -->
                  <el-form-item>
                    <el-checkbox v-model="fileForm.force_update">
                      强制更新（目前对于重叠日期采用替换策略）
                    </el-checkbox>
                  </el-form-item>

                  <!-- 指标数据生成选项 -->
                  <el-form-item label="指标数据生成">
                    <div class="flex items-center mb-2">
                      <el-checkbox 
                        v-model="isAllFileIndicatorsSelected" 
                        :indeterminate="isFileIndicatorsIndeterminate"
                        @change="handleSelectAllFileIndicators"
                      >
                        全选
                      </el-checkbox>
                    </div>
                    <el-checkbox-group v-model="safeFileIndicators">
                      <el-checkbox value="ma">MA移动平均线</el-checkbox>
                      <el-checkbox value="mavol">MAVOL成交量移动平均线</el-checkbox>
                      <el-checkbox value="kdj">KDJ随机指标</el-checkbox>
                      <el-checkbox value="rsi">RSI相对强弱指标</el-checkbox>
                      <el-checkbox value="boll">BOLL布林带</el-checkbox>
                      <el-checkbox value="pvfrs">PVFRS指标</el-checkbox>
                      <el-checkbox value="icost">无穷成本均线</el-checkbox>
                    </el-checkbox-group>
                    <div class="text-sm text-gray-500 mt-1">选择需要同时生成的技术指标数据</div>
                  </el-form-item>

                  <!-- 操作按钮 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="fileLoading"
                      :disabled="currentTaskIsRunning"
                      @click="startFileCollection"
                    >
                      <el-icon v-if="fileLoading" class="mr-2"><Loading /></el-icon>
                      {{ fileLoading ? '启动中...' : (currentTaskIsRunning ? '等待当前任务完成' : '开始采集') }}
                    </el-button>
                    <el-button @click="resetFileForm">重置</el-button>
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
                  :disabled="currentTaskIsRunning"
                  @click="startAShareRealtimeCollection"
                >
                  <el-icon v-if="ashareRealtimeLoading" class="mr-2"><Loading /></el-icon>
                  {{ ashareRealtimeLoading ? '启动中...' : (currentTaskIsRunning ? '等待当前任务完成' : '开始采集') }}
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
                      :disabled="currentTaskIsRunning"
                      @click="startHKCollection"
                    >
                      <el-icon v-if="hkLoading" class="mr-2"><Loading /></el-icon>
                      {{ hkLoading ? '启动中...' : (currentTaskIsRunning ? '等待当前任务完成' : '开始采集') }}
                    </el-button>
                    <el-button @click="resetHKForm">重置</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-card>
          </el-tab-pane>

          <el-tab-pane label="港股历史数据采集-文件" name="hk_file">
            <el-card>
              <div class="text-center mb-8">
                <el-icon class="text-6xl text-gray-400 mb-4"><DocumentCopy /></el-icon>
                <h2 class="text-2xl font-bold text-gray-900 mb-2">港股历史数据采集-文件</h2>
                <p class="text-gray-600">从本地TXT/CSV/XLSX文件批量导入港股历史行情数据</p>
              </div>

              <!-- 文件上传区域 -->
              <div class="max-w-2xl mx-auto mb-8">
                <el-card shadow="never" class="bg-blue-50 border-blue-100">
                  <template #header>
                    <div class="flex items-center">
                      <el-icon class="text-blue-500 mr-2"><Upload /></el-icon>
                      <span class="font-bold text-blue-700">文件上传说明</span>
                    </div>
                  </template>
                  <div class="text-sm text-blue-600 space-y-2">
                    <p>1. 请先将港股行情数据文件（.txt、.csv 或 .xlsx）上传到服务器指定的目录：<code class="bg-blue-100 px-1 rounded">backend_core/data/</code></p>
                    <p>2. 文件名可为<strong>单日</strong>（如 <code class="bg-blue-100 px-1 rounded">hk_historical_quotes_20260205.xlsx</code>）或<strong>日期区间</strong>（如 <code class="bg-blue-100 px-1 rounded">hk_historical_quotes_2026-02-10_to_2026-02-13.xlsx</code>）；区间内每个交易日会匹配同一文件。</p>
                    <p>3. <strong>CSV/XLSX</strong> 多日期合并文件须含「日期 / trade_date / date」列；系统按<strong>当前循环日</strong>只导入该日行，不会把其它交易日写入当天。</p>
                    <p>4. 若目录下仅有<strong>一个</strong> <code class="bg-blue-100 px-1 rounded">hk_historical_quotes*</code> 文件且无单日名匹配时，会作为汇总表按行内日期拆分导入。</p>
                  </div>
                  <div class="mt-4 flex justify-center">
                    <el-upload
                      class="upload-demo"
                      :action="API_BASE + '/api/data-collection/upload-historical-file'"
                      multiple
                      :limit="50"
                      :show-file-list="true"
                      :on-success="handleFileUploadSuccess"
                      :on-error="handleFileUploadError"
                    >
                      <el-button type="primary" plain>
                        <el-icon class="mr-1"><UploadFilled /></el-icon>
                        上传文件到服务器
                      </el-button>
                    </el-upload>
                  </div>
                </el-card>
              </div>

              <!-- 港股文件采集表单 -->
              <div class="max-w-2xl mx-auto">
                <el-form label-width="120px">
                  <!-- 日期范围 -->
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="开始日期" required>
                        <el-date-picker
                          v-model="hkFileForm.start_date"
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
                          v-model="hkFileForm.end_date"
                          type="date"
                          placeholder="选择结束日期"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <el-form-item label="文件类型" required>
                    <el-radio-group v-model="hkFileForm.file_type">
                      <el-radio value="txt">TXT 文件</el-radio>
                      <el-radio value="csv">CSV 文件</el-radio>
                      <el-radio value="xlsx">Excel (.xlsx) 文件</el-radio>
                    </el-radio-group>
                  </el-form-item>

                  <el-form-item label="技术指标">
                    <div class="border rounded p-4 bg-gray-50 w-full">
                      <div class="flex items-center mb-3 pb-2 border-b border-gray-200">
                        <el-checkbox
                          v-model="isAllHKFileIndicatorsSelected"
                          :indeterminate="isHKFileIndicatorsIndeterminate"
                          @change="handleSelectAllHKFileIndicators"
                        >
                          <span class="font-bold">全选指标</span>
                        </el-checkbox>
                      </div>
                      <el-checkbox-group v-model="safeHKFileIndicators">
                        <el-row :gutter="20">
                          <el-col :span="8"><el-checkbox value="ma">MA (均线)</el-checkbox></el-col>
                          <el-col :span="8"><el-checkbox value="mavol">MAVOL (成交量均线)</el-checkbox></el-col>
                          <el-col :span="8"><el-checkbox value="pvfrs">PVFRS (GMS 策略指标)</el-checkbox></el-col>
                        </el-row>
                        <el-row :gutter="20" class="mt-2">
                          <el-col :span="8"><el-checkbox value="kdj">KDJ (随机指标)</el-checkbox></el-col>
                          <el-col :span="8"><el-checkbox value="rsi">RSI (相对强弱指标)</el-checkbox></el-col>
                          <el-col :span="8"><el-checkbox value="boll">BOLL (布林线)</el-checkbox></el-col>
                          <el-col :span="8"><el-checkbox value="icost">无穷成本均线</el-checkbox></el-col>
                        </el-row>
                      </el-checkbox-group>
                    </div>
                    <div class="text-xs text-gray-400 mt-1">
                      <el-icon class="mr-1"><InfoFilled /></el-icon>
                      采集完成后将自动计算选中的技术指标
                    </div>
                  </el-form-item>

                  <el-form-item>
                    <el-checkbox v-model="hkFileForm.force_update">
                      强制更新（如果已存在此日期的数据，将重新插入）
                    </el-checkbox>
                  </el-form-item>

                  <!-- 操作按钮 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="hkFileLoading"
                      :disabled="currentTaskIsRunning"
                      @click="startHKFileHistoricalCollection"
                    >
                      <el-icon v-if="hkFileLoading" class="mr-2"><Loading /></el-icon>
                      {{ hkFileLoading ? '启动中...' : (currentTaskIsRunning ? '等待当前任务完成' : '开始采集') }}
                    </el-button>
                    <el-button @click="resetHKFileForm">重置</el-button>
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
                  :disabled="currentTaskIsRunning"
                  @click="startHKRealtimeCollection"
                >
                  <el-icon v-if="hkRealtimeLoading" class="mr-2"><Loading /></el-icon>
                  {{ hkRealtimeLoading ? '启动中...' : (currentTaskIsRunning ? '等待当前任务完成' : '开始采集') }}
                </el-button>
                <el-button @click="resetHKRealtimeForm">重置</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- ETF基金数据采集 -->
      <el-tab-pane label="ETF基金数据采集" name="etf">
        <el-card>
          <div class="text-center mb-8">
            <el-icon class="text-6xl text-green-400 mb-4"><DataAnalysis /></el-icon>
            <h2 class="text-2xl font-bold text-gray-900 mb-2">ETF基金数据采集</h2>
            <p class="text-gray-600">采集ETF基金列表、历史行情数据并计算技术指标</p>
          </div>

          <!-- ETF 统计卡片 -->
          <div class="grid grid-cols-4 gap-4 mb-6" v-if="etfStats">
            <el-card shadow="never" class="bg-blue-50 border-blue-100 text-center">
              <div class="text-2xl font-bold text-blue-600">{{ etfStats.total_funds || 0 }}</div>
              <div class="text-xs text-gray-500 mt-1">ETF总数</div>
            </el-card>
            <el-card shadow="never" class="bg-green-50 border-green-100 text-center">
              <div class="text-2xl font-bold text-green-600">{{ etfStats.active_funds || 0 }}</div>
              <div class="text-xs text-gray-500 mt-1">已启用</div>
            </el-card>
            <el-card shadow="never" class="bg-purple-50 border-purple-100 text-center">
              <div class="text-2xl font-bold text-purple-600">{{ etfStats.historical_records || 0 }}</div>
              <div class="text-xs text-gray-500 mt-1">历史行情条数</div>
            </el-card>
            <el-card shadow="never" class="bg-orange-50 border-orange-100 text-center">
              <div class="text-sm font-bold text-orange-600">{{ etfStats.latest_date || '暂无' }}</div>
              <div class="text-xs text-gray-500 mt-1">最新数据日期</div>
            </el-card>
          </div>

          <!-- ETF 任务状态 -->
          <el-alert
            v-if="etfTaskStatus.is_running"
            :title="etfTaskStatus.message || '任务进行中...'"
            type="warning"
            :closable="false"
            show-icon
            class="mb-4"
          />
          <el-alert
            v-if="!etfTaskStatus.is_running && etfTaskStatus.result"
            :title="etfTaskStatus.message || '任务已完成'"
            :type="etfTaskStatus.result?.error ? 'error' : 'success'"
            :closable="true"
            show-icon
            class="mb-4"
          />

          <div class="max-w-2xl mx-auto">
            <!-- 第一步：同步ETF列表 -->
            <el-divider content-position="left">
              <el-tag type="primary" size="large">第1步：同步ETF列表</el-tag>
            </el-divider>
            <el-form label-width="120px" class="mb-6">
              <el-form-item>
                <el-button
                  type="success"
                  :loading="etfSyncLoading"
                  :disabled="etfTaskStatus.is_running"
                  @click="syncETFList"
                >
                  <el-icon v-if="etfSyncLoading" class="mr-2"><Loading /></el-icon>
                  {{ etfSyncLoading ? '同步中...' : (etfTaskStatus.is_running ? '等待任务完成' : '同步ETF列表') }}
                </el-button>
                <span class="text-sm text-gray-500 ml-3">从东方财富获取最新ETF列表并入库</span>
              </el-form-item>
            </el-form>

            <!-- 第二步：历史行情采集 -->
            <el-divider content-position="left">
              <el-tag type="primary" size="large">第2步：历史行情采集</el-tag>
            </el-divider>
            <el-form @submit.prevent="startETFCollection" :model="etfForm" label-width="120px">
              <!-- 日期范围 -->
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="开始日期" required>
                    <el-date-picker
                      v-model="etfForm.start_date"
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
                      v-model="etfForm.end_date"
                      type="date"
                      placeholder="选择结束日期"
                      format="YYYY-MM-DD"
                      value-format="YYYY-MM-DD"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
              </el-row>

              <!-- ETF选择 -->
              <el-form-item label="采集范围">
                <el-radio-group v-model="etfForm.collection_type">
                  <el-radio value="all">全量ETF采集</el-radio>
                  <el-radio value="specified">指定ETF代码</el-radio>
                </el-radio-group>
              </el-form-item>

              <!-- 指定ETF代码输入 -->
              <el-form-item v-if="etfForm.collection_type === 'specified'" label="ETF代码" required>
                <el-input
                  v-model="etfForm.etf_codes_text"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入ETF代码，每行一个，例如：&#10;510300&#10;159919&#10;512100"
                />
                <div class="text-sm text-gray-500 mt-1">支持输入多个ETF代码，每行一个</div>
              </el-form-item>

              <!-- 全量采集说明 -->
              <el-alert
                v-if="etfForm.collection_type === 'all'"
                title="全量采集说明"
                type="info"
                :closable="false"
                show-icon
                class="mb-4"
              >
                <p>将采集数据库中所有已启用的ETF历史行情数据，采集完成后自动计算所有技术指标（MA/MAVOL/MACD/KDJ/RSI/BOLL/GMS均值频率共振）。</p>
              </el-alert>

              <!-- 操作按钮 -->
              <el-form-item>
                <el-button
                  type="primary"
                  :loading="etfCollectLoading"
                  :disabled="etfTaskStatus.is_running"
                  @click="startETFCollection"
                >
                  <el-icon v-if="etfCollectLoading" class="mr-2"><Loading /></el-icon>
                  {{ etfCollectLoading ? '启动中...' : (etfTaskStatus.is_running ? '等待任务完成' : '开始采集') }}
                </el-button>
                <el-button @click="resetETFForm">重置</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 采集日历管理 -->
      <el-tab-pane label="采集日历管理" name="calendar">
        <el-card>
          <div class="text-center mb-6">
            <el-icon class="text-5xl text-indigo-400 mb-3"><Calendar /></el-icon>
            <h2 class="text-2xl font-bold text-gray-900 mb-1">采集日历管理</h2>
            <p class="text-gray-500">设置 A 股和港股的节假日，采集任务将自动跳过节假日</p>
          </div>

          <!-- 工具栏 -->
          <div class="flex items-center gap-3 mb-4 flex-wrap">
            <el-radio-group v-model="calendarMarket" @change="loadCalendar">
              <el-radio-button value="CN">A 股（CN）</el-radio-button>
              <el-radio-button value="HK">港股（HK）</el-radio-button>
            </el-radio-group>
            <el-date-picker
              v-model="calendarFilterYear"
              type="year"
              placeholder="筛选年份"
              format="YYYY"
              value-format="YYYY"
              clearable
              style="width:120px"
              @change="loadCalendar"
            />
            <el-button type="primary" :icon="Plus" @click="openAddHolidayDialog">新增节假日</el-button>
            <el-button :icon="Refresh" @click="loadCalendar">刷新</el-button>
            <el-button type="warning" plain :icon="UploadFilled" @click="openBatchImportDialog">批量导入</el-button>
            <el-button type="success" plain :icon="Download" @click="exportCalendar">批量导出</el-button>
          </div>

          <!-- 节假日表格 -->
          <el-table
            :data="calendarList"
            v-loading="calendarLoading"
            border
            stripe
            style="width:100%"
            empty-text="暂无节假日数据"
          >
            <el-table-column label="市场" prop="market" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.market === 'CN' ? 'primary' : 'warning'" size="small">
                  {{ row.market === 'CN' ? 'A股' : '港股' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="节假日日期" prop="holiday_date" width="150" align="center" />
            <el-table-column label="说明" prop="description" min-width="200" />
            <el-table-column label="添加时间" prop="created_at" width="180" align="center">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="130" align="center">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openEditHolidayDialog(row)">编辑</el-button>
                <el-button type="danger" link size="small" @click="deleteHoliday(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="mt-3 text-gray-400 text-xs">
            <el-icon class="mr-1"><InfoFilled /></el-icon>
            共 {{ calendarList.length }} 条节假日记录。采集任务执行时会自动从数据库读取节假日，匹配当时日期则跳过采集。
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

  <!-- 新增/编辑节假日对话框 -->
  <el-dialog
    v-model="holidayDialogVisible"
    :title="holidayDialogMode === 'add' ? '新增节假日' : '编辑节假日'"
    width="480px"
    destroy-on-close
  >
    <el-form :model="holidayForm" label-width="100px" label-position="right">
      <el-form-item label="市场" required>
        <el-radio-group v-model="holidayForm.market">
          <el-radio value="CN">A股（CN）</el-radio>
          <el-radio value="HK">港股（HK）</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="节假日日期" required>
        <el-date-picker
          v-model="holidayForm.holiday_date"
          type="date"
          placeholder="选择节假日日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          style="width:100%"
        />
      </el-form-item>
      <el-form-item label="说明">
        <el-input
          v-model="holidayForm.description"
          placeholder="例如：春节假期、国庆节等"
          clearable
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="holidayDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="holidaySaving" @click="saveHoliday">
        {{ holidayDialogMode === 'add' ? '添加' : '保存' }}
      </el-button>
    </template>
  </el-dialog>

  <!-- 批量导入对话框 -->
  <el-dialog v-model="batchImportDialogVisible" title="批量导入节假日" width="560px" destroy-on-close>
    <div class="mb-4 text-sm text-gray-500">
      <div class="flex items-end justify-between">
        <div>
          <p class="mb-1">请按以下格式填写，或上传CSV/TXT文件（市场,日期,说明）：</p>
          <pre class="bg-gray-50 border rounded p-2 text-xs mb-0">CN,2026-01-01,元旦
CN,2026-01-28,春节
HK,2026-01-01,New Year's Day</pre>
        </div>
        <el-upload
          action=""
          :auto-upload="false"
          :show-file-list="false"
          accept=".csv,.txt"
          :on-change="handleCalendarFileChange"
        >
          <el-button type="success" size="small" plain>导入CSV文件</el-button>
        </el-upload>
      </div>
    </div>
    <el-input
      v-model="batchImportText"
      type="textarea"
      :rows="10"
      placeholder="市场,日期,说明&#10;CN,2026-01-01,元旦&#10;HK,2026-01-01,New Year's Day"
    />
    <div class="mt-2 text-xs text-gray-400">市场填 CN 或 HK；日期格式 YYYY-MM-DD；说明可选</div>
    <template #footer>
      <el-button @click="batchImportDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="batchImporting" @click="executeBatchImport">
        开始导入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
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
  Refresh,
  UploadFilled,
  Calendar,
  Plus,
  Download,
  InfoFilled
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

// 文件数据采集表单
interface FileFormData {
  start_date: string
  end_date: string
  force_update: boolean
  indicators: string[]
  file_type: string
}

const fileForm = ref<FileFormData>({
  start_date: '',
  end_date: '',
  force_update: false,
  indicators: [],
  file_type: 'txt'
})

const hkFileForm = ref<FileFormData>({
  start_date: '',
  end_date: '',
  force_update: false,
  indicators: [],
  file_type: 'txt'
})

// 状态数据
const tasks = ref<Task[]>([])
const currentTask = ref<CurrentTask | null>(null)
/** 仅 status===running 视为占用；避免任务结束后未刷新接口时仍误判为「有任务」 */
const currentTaskIsRunning = computed(() => currentTask.value?.status === 'running')
const loading = ref(false)
const hkLoading = ref(false)
const tushareLoading = ref(false)
const fileLoading = ref(false)
const ashareRealtimeLoading = ref(false)
const hkRealtimeLoading = ref(false)
const hkFileLoading = ref(false)
const pollingInterval = ref<NodeJS.Timeout | null>(null)

// ETF 相关数据
const etfSyncLoading = ref(false)
const etfCollectLoading = ref(false)
const etfStats = ref<any>(null)
const etfTaskStatus = ref<any>({ is_running: false, message: '', result: null })
const etfForm = ref({
  start_date: '',
  end_date: '',
  collection_type: 'all' as 'all' | 'specified',
  etf_codes_text: ''
})
let etfPollingTimer: NodeJS.Timeout | null = null

// 计算属性
const allIndicators = ['ma', 'mavol', 'kdj', 'rsi', 'boll', 'pvfrs', 'icost']

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

// 文件表单指标选择
const safeFileIndicators = computed<string[]>({
  get: () => {
    const indicators = fileForm.value.indicators
    return Array.isArray(indicators) ? indicators : []
  },
  set: (val: string[]) => {
    fileForm.value.indicators = Array.isArray(val) ? val : []
  }
})

const isFileIndicatorsIndeterminate = computed(() => {
  const indicators = safeFileIndicators.value
  const selectedCount = indicators.length
  if (selectedCount === 0) {
    return false
  } else if (selectedCount === allIndicators.length) {
    return false
  } else {
    return true
  }
})

const isAllFileIndicatorsSelected = computed(() => {
  return safeFileIndicators.value.length === allIndicators.length
})

const handleSelectAllFileIndicators = (checked: boolean | string | number | boolean[] | undefined) => {
  const isChecked = typeof checked === 'boolean' ? checked : Boolean(checked)
  if (isChecked) {
    safeFileIndicators.value = [...allIndicators]
  } else {
    safeFileIndicators.value = []
  }
}

// 港股文件表单指标选择
const safeHKFileIndicators = computed<string[]>({
  get: () => {
    const indicators = hkFileForm.value.indicators
    return Array.isArray(indicators) ? indicators : []
  },
  set: (val: string[]) => {
    hkFileForm.value.indicators = Array.isArray(val) ? val : []
  }
})

const isHKFileIndicatorsIndeterminate = computed(() => {
  const indicators = safeHKFileIndicators.value
  const selectedCount = indicators.length
  if (selectedCount === 0) {
    return false
  } else if (selectedCount === allIndicators.length) {
    return false
  } else {
    return true
  }
})

const isAllHKFileIndicatorsSelected = computed(() => {
  return safeHKFileIndicators.value.length === allIndicators.length
})

const handleSelectAllHKFileIndicators = (checked: boolean | string | number | boolean[] | undefined) => {
  const isChecked = typeof checked === 'boolean' ? checked : Boolean(checked)
  if (isChecked) {
    safeHKFileIndicators.value = [...allIndicators]
  } else {
    safeHKFileIndicators.value = []
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
    if (currentTaskIsRunning.value) {
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

    if (currentTaskIsRunning.value) {
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
    if (currentTaskIsRunning.value) {
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

const resetFileForm = () => {
  fileForm.value = {
    start_date: '',
    end_date: '',
    force_update: false,
    indicators: [],
    file_type: 'txt'
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
    if (currentTaskIsRunning.value) {
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

const beforeFileUpload = (file: File) => {
  const isTxt = file.name.endsWith('.txt')
  const isCsv = file.name.endsWith('.csv')
  const isXlsx = file.name.endsWith('.xlsx')
  if (!isTxt && !isCsv && !isXlsx) {
    ElMessage.error('只能上传 TXT、CSV 或 XLSX 文件!')
    return false
  }
  // 校验文件名格式 daily_YYYYMMDD 或 historical_quotes_YYYY-MM-DD 等
  const namePattern = /^(daily_|historical_quotes_)\d{4}-?\d{2}-?\d{2}\.(txt|csv|xlsx)$/
  if (!namePattern.test(file.name)) {
    ElMessage.warning(`文件名 ${file.name} 不符合建议格式 (如 daily_20231027 或 historical_quotes_2023-10-27)，采集任务可能无法自动匹配。`)
  }
  return true
}

const handleFileUploadSuccess = (response: any) => {
  if (response.success) {
    ElMessage.success(response.message || '文件上传成功')
  } else {
    ElMessage.error(response.message || '文件上传失败')
  }
}

const handleFileUploadError = (error: any) => {
  console.error('文件上传失败:', error)
  ElMessage.error('文件上传过程出错，请检查网络或后端接口')
}

const startFileCollection = async () => {
  try {
    fileLoading.value = true
    
    // 验证表单
    if (!fileForm.value.start_date || !fileForm.value.end_date) {
      ElMessage.error('请选择开始日期和结束日期')
      return
    }
    
    // 检查当前任务状态
    if (currentTaskIsRunning.value) {
      ElMessage.error('已有采集任务正在运行，请等待完成后再启动新任务')
      return
    }

    console.log('发送文件采集请求:', fileForm.value)
    
    // 指标
    const indicatorsToRun = safeFileIndicators.value

    const response = await axios.post(`${API_BASE}/api/data-collection/file-historical`, {
      start_date: fileForm.value.start_date,
      end_date: fileForm.value.end_date,
      force_update: fileForm.value.force_update,
      indicators: indicatorsToRun,
      file_type: fileForm.value.file_type
    })
    
    if (response.data.status === 'started') {
      ElMessage.success('历史数据采集(文件)任务已启动')
      loadTasks()
      loadCurrentTask()
    }
    
  } catch (error: any) {
    console.error('启动历史数据采集(文件)任务失败:', error)
    let errorMsg = '启动历史数据采集(文件)任务失败'
    
    if (error.response) {
      errorMsg = error.response.data?.detail || `服务器错误 (${error.response.status})`
    } else if (error.request) {
      errorMsg = '无法连接到服务器，请检查网络连接'
    } else {
      errorMsg = error.message || '未知错误'
    }
    
    ElMessage.error(errorMsg)
  } finally {
    fileLoading.value = false
  }
}

const startHKFileHistoricalCollection = async () => {
  try {
    hkFileLoading.value = true
    
    // 验证表单
    if (!hkFileForm.value.start_date || !hkFileForm.value.end_date) {
      ElMessage.error('请选择开始日期和结束日期')
      return
    }
    
    // 检查当前任务状态
    if (currentTaskIsRunning.value) {
      ElMessage.error('已有采集任务正在运行，请等待完成后再启动新任务')
      return
    }

    console.log('发送港股文件采集请求:', hkFileForm.value)
    
    const response = await axios.post(`${API_BASE}/api/data-collection/historical/hk-file`, {
      start_date: hkFileForm.value.start_date,
      end_date: hkFileForm.value.end_date,
      force_update: hkFileForm.value.force_update,
      indicators: safeHKFileIndicators.value,
      file_type: hkFileForm.value.file_type
    })
    
    if (response.data.status === 'started') {
      ElMessage.success('港股历史数据采集(文件)任务已启动')
      loadTasks()
      loadCurrentTask()
    }
    
  } catch (error: any) {
    console.error('启动港股历史数据采集(文件)任务失败:', error)
    ElMessage.error(error.response?.data?.detail || '启动港股历史数据采集(文件)任务失败')
  } finally {
    hkFileLoading.value = false
  }
}

const resetHKFileForm = () => {
  hkFileForm.value = {
    start_date: '',
    end_date: '',
    file_type: 'txt',
    force_update: false,
    indicators: []
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

/*
const startPolling = () => {
  // 仅在任务运行时轮询 current-task，避免频繁刷接口导致日志/网络压力过大
  const tick = async () => {
    await loadCurrentTask()
    // 当任务不处于运行中时停止轮询，并在停止前刷新任务列表一次
    if (currentTask.value && currentTask.value.status && currentTask.value.status !== 'running') {
      stopPolling()
      await loadTasks()
    }
  }
  // 每 15 秒刷新一次（生产环境建议更长轮询间隔）
  pollingInterval.value = setInterval(tick, 15000)
}
*/

const stopPolling = () => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
}

// 有运行中任务时定时同步 current-task / 任务列表，结束后自动清空界面状态
watch(
  currentTaskIsRunning,
  (running) => {
    stopPolling()
    if (running) {
      pollingInterval.value = setInterval(async () => {
        await loadCurrentTask()
        await loadTasks()
      }, 12000)
    }
  },
  { immediate: true }
)

// 生命周期
onMounted(() => {
  loadTasks()
  loadCurrentTask()
  loadCalendar()
})

// ============================================================
// 采集日历管理
// ============================================================
interface CalendarItem {
  id: number
  market: string
  holiday_date: string
  description: string | null
  created_at: string
  updated_at: string
}

interface HolidayForm {
  market: string
  holiday_date: string
  description: string
}

const calendarMarket = ref<string>('CN')
const calendarFilterYear = ref<string>('')
const calendarList = ref<CalendarItem[]>([])
const calendarLoading = ref(false)

// 对话框状态
const holidayDialogVisible = ref(false)
const holidayDialogMode = ref<'add' | 'edit'>('add')
const holidaySaving = ref(false)
const editingHolidayId = ref<number | null>(null)
const holidayForm = ref<HolidayForm>({
  market: 'CN',
  holiday_date: '',
  description: ''
})

// 批量导入状态
const batchImportDialogVisible = ref(false)
const batchImporting = ref(false)
const batchImportText = ref('')

const getAuthHeader = () => {
  const token = localStorage.getItem('admin_token') || localStorage.getItem('token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const loadCalendar = async () => {
  calendarLoading.value = true
  try {
    const params: Record<string, string> = { market: calendarMarket.value }
    if (calendarFilterYear.value) {
      params.start_date = `${calendarFilterYear.value}-01-01`
      params.end_date = `${calendarFilterYear.value}-12-31`
    }
    const res = await axios.get(`${API_BASE}/api/admin/trading-calendar/list`, {
      params,
      headers: getAuthHeader()
    })
    calendarList.value = res.data || []
  } catch (err: any) {
    ElMessage.error(`加载采集日历失败: ${err?.response?.data?.detail || err.message}`)
  } finally {
    calendarLoading.value = false
  }
}

const openAddHolidayDialog = () => {
  holidayDialogMode.value = 'add'
  editingHolidayId.value = null
  holidayForm.value = { market: calendarMarket.value, holiday_date: '', description: '' }
  holidayDialogVisible.value = true
}

const openEditHolidayDialog = (row: CalendarItem) => {
  holidayDialogMode.value = 'edit'
  editingHolidayId.value = row.id
  holidayForm.value = {
    market: row.market,
    holiday_date: row.holiday_date,
    description: row.description || ''
  }
  holidayDialogVisible.value = true
}

const saveHoliday = async () => {
  if (!holidayForm.value.holiday_date) {
    ElMessage.warning('请选择节假日日期')
    return
  }
  holidaySaving.value = true
  try {
    if (holidayDialogMode.value === 'add') {
      await axios.post(
        `${API_BASE}/api/admin/trading-calendar/add`,
        holidayForm.value,
        { headers: getAuthHeader() }
      )
      ElMessage.success('节假日添加成功')
    } else {
      await axios.put(
        `${API_BASE}/api/admin/trading-calendar/update/${editingHolidayId.value}`,
        holidayForm.value,
        { headers: getAuthHeader() }
      )
      ElMessage.success('节假日更新成功')
    }
    holidayDialogVisible.value = false
    await loadCalendar()
  } catch (err: any) {
    ElMessage.error(`操作失败: ${err?.response?.data?.detail || err.message}`)
  } finally {
    holidaySaving.value = false
  }
}

const deleteHoliday = async (row: CalendarItem) => {
  try {
    await ElMessageBox.confirm(
      `确认删除 [${row.market}] ${row.holiday_date}${row.description ? ' (' + row.description + ')' : ''} 的节假日设置？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await axios.delete(
      `${API_BASE}/api/admin/trading-calendar/delete/${row.id}`,
      { headers: getAuthHeader() }
    )
    ElMessage.success('删除成功')
    await loadCalendar()
  } catch (err: any) {
    ElMessage.error(`删除失败: ${err?.response?.data?.detail || err.message}`)
  }
}

const openBatchImportDialog = () => {
  batchImportText.value = ''
  batchImportDialogVisible.value = true
}

const handleCalendarFileChange = (file: any) => {
  if (!file || !file.raw) return
  const rawFile = file.raw
  const reader = new FileReader()
  reader.onload = (e) => {
    const text = e.target?.result as string
    if (text) {
      // 保留原来的内容，追加换行后再附加上传内容
      batchImportText.value = batchImportText.value 
        ? batchImportText.value + '\n' + text 
        : text
      ElMessage.success('文件读取成功，请确认导入内容')
    }
  }
  reader.onerror = () => {
    ElMessage.error('文件读取失败')
  }
  // 使用 UTF-8 读取通常的逗号分隔 CSV，或者 ANSI 也可以，这里默认 utf-8
  reader.readAsText(rawFile, 'utf-8')
}

const executeBatchImport = async () => {
  const lines = batchImportText.value.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'))
  if (!lines.length) {
    ElMessage.warning('请填写至少一行节假日数据')
    return
  }
  const rows: HolidayForm[] = []
  const errors: string[] = []
  for (const line of lines) {
    const parts = line.split(',')
    const market = (parts[0] || '').trim().toUpperCase()
    const date = (parts[1] || '').trim()
    const desc = (parts[2] || '').trim()
    if (!['CN', 'HK'].includes(market)) { errors.push(`市场无效: ${line}`); continue }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) { errors.push(`日期格式错误: ${line}`); continue }
    rows.push({ market, holiday_date: date, description: desc })
  }
  if (errors.length) {
    ElMessage.error(`以下行格式有误:\n${errors.slice(0, 5).join('\n')}${errors.length > 5 ? '\n...' : ''}`)
    return
  }
  batchImporting.value = true
  let successCount = 0, skipCount = 0, failCount = 0
  for (const row of rows) {
    try {
      await axios.post(`${API_BASE}/api/admin/trading-calendar/add`, row, { headers: getAuthHeader() })
      successCount++
    } catch (err: any) {
      const msg = err?.response?.data?.detail || ''
      if (msg.includes('已存在')) { skipCount++ } else { failCount++ }
    }
  }
  batchImporting.value = false
  batchImportDialogVisible.value = false
  ElMessage.success(`批量导入完成: 新增 ${successCount}，跳过已存在 ${skipCount}，失败 ${failCount}`)
  await loadCalendar()
}

const exportCalendar = () => {
  if (calendarList.value.length === 0) {
    ElMessage.warning('当前列表无节假日数据可导出')
    return
  }
  // 按照 '市场,日期,说明' 的格式拼接
  const lines = calendarList.value.map(item => {
    return `${item.market},${item.holiday_date},${item.description || ''}`
  })
  const textContent = lines.join('\n')
  
  // 创建并触发下载
  const blob = new Blob([textContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.setAttribute('href', url)
  
  const currentDate = new Date().toISOString().split('T')[0]
  link.setAttribute('download', `trading_calendar_${calendarMarket.value}_${currentDate}.csv`)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  
  ElMessage.success('导出成功')
}

// ============== ETF 相关方法 ==============

const loadETFStats = async () => {
  try {
    const res = await axios.get(`${API_BASE}/api/admin/etf/stats`)
    if (res.data?.success) {
      etfStats.value = res.data.data
    }
  } catch (e) {
    console.warn('加载ETF统计失败', e)
  }
}

const pollETFTaskStatus = async () => {
  try {
    const res = await axios.get(`${API_BASE}/api/admin/etf/task-status`)
    if (res.data?.success) {
      etfTaskStatus.value = res.data.data
      if (!res.data.data.is_running && etfPollingTimer) {
        clearInterval(etfPollingTimer)
        etfPollingTimer = null
        etfSyncLoading.value = false
        etfCollectLoading.value = false
        // 任务完成后刷新统计
        await loadETFStats()
      }
    }
  } catch (e) {
    console.warn('查询ETF任务状态失败', e)
  }
}

const startETFPolling = () => {
  if (etfPollingTimer) clearInterval(etfPollingTimer)
  etfPollingTimer = setInterval(pollETFTaskStatus, 3000)
}

const syncETFList = async () => {
  try {
    etfSyncLoading.value = true
    const res = await axios.post(`${API_BASE}/api/admin/etf/sync-list`)
    if (res.data?.success) {
      ElMessage.success('ETF列表同步任务已启动')
      startETFPolling()
    } else {
      ElMessage.error(res.data?.detail || '同步启动失败')
      etfSyncLoading.value = false
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'ETF列表同步失败')
    etfSyncLoading.value = false
  }
}

const startETFCollection = async () => {
  if (!etfForm.value.start_date || !etfForm.value.end_date) {
    ElMessage.warning('请选择日期范围')
    return
  }

  let etf_codes: string[] | null = null
  if (etfForm.value.collection_type === 'specified') {
    const text = etfForm.value.etf_codes_text.trim()
    if (!text) {
      ElMessage.warning('请输入ETF代码')
      return
    }
    etf_codes = text.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)
    if (etf_codes.length === 0) {
      ElMessage.warning('请输入有效的ETF代码')
      return
    }
  }

  try {
    etfCollectLoading.value = true
    const res = await axios.post(`${API_BASE}/api/admin/etf/collect`, {
      start_date: etfForm.value.start_date,
      end_date: etfForm.value.end_date,
      etf_codes: etf_codes
    })
    if (res.data?.success) {
      ElMessage.success('ETF行情采集任务已启动')
      startETFPolling()
    } else {
      ElMessage.error(res.data?.detail || '采集启动失败')
      etfCollectLoading.value = false
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'ETF行情采集失败')
    etfCollectLoading.value = false
  }
}

const resetETFForm = () => {
  etfForm.value = {
    start_date: '',
    end_date: '',
    collection_type: 'all',
    etf_codes_text: ''
  }
}

// 切到 ETF 标签页时自动加载统计
watch(() => activeMainTab.value, (val) => {
  if (val === 'etf') {
    loadETFStats()
    pollETFTaskStatus()
  }
})

onUnmounted(() => {
  stopPolling()
  if (etfPollingTimer) {
    clearInterval(etfPollingTimer)
    etfPollingTimer = null
  }
})

</script>

<style scoped>
.datacollect-view {
  padding: 20px;
}
</style>