<template>
  <div class="datacollect-view">
    <!-- 褰撳墠浠诲姟鐘舵€?-->
    <div v-if="currentTask" class="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
      <div class="flex items-center">
        <el-icon class="text-yellow-600 mr-3"><Warning /></el-icon>
        <div>
          <h3 class="text-sm font-medium text-yellow-800">褰撳墠鏈変换鍔℃鍦ㄨ繍琛?/h3>
          <p class="text-sm text-yellow-700 mt-1">
            浠诲姟ID: {{ currentTask.task_id }} | 
            寮€濮嬫椂闂? {{ formatTime(currentTask.start_time) }}
          </p>
        </div>
      </div>
    </div>

    <!-- 鏍囩椤?-->
    <el-tabs v-model="activeMainTab" class="mb-8">
      <!-- A鑲″巻鍙叉暟鎹噰闆?-->
      <el-tab-pane label="A鑲″巻鍙叉暟鎹噰闆? name="ashare">
        <el-tabs v-model="activeAShareTab">
          <!-- AkShare鏍囩椤?-->
          <el-tab-pane label="鍘嗗彶鏁版嵁閲囬泦-AkShare" name="akshare">
            <el-card>
              <div class="text-center mb-8">
                <el-icon class="text-6xl text-gray-400 mb-4"><DataAnalysis /></el-icon>
                <h2 class="text-2xl font-bold text-gray-900 mb-2">鍘嗗彶鏁版嵁閲囬泦-AkShare</h2>
                <p class="text-gray-600">浣跨敤akshare閲囬泦A鑲″巻鍙茶鎯呮暟鎹紙鍗曚换鍔℃墽琛岋紝闃查噸澶嶉噰闆嗭級</p>
              </div>

              <!-- 閲囬泦閰嶇疆琛ㄥ崟 -->
              <div class="max-w-2xl mx-auto">
                <el-form @submit.prevent="startCollection" :model="form" label-width="120px">
                  <!-- 鏃ユ湡鑼冨洿 -->
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="寮€濮嬫棩鏈? required>
                        <el-date-picker
                          v-model="form.start_date"
                          type="date"
                          placeholder="閫夋嫨寮€濮嬫棩鏈?
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="缁撴潫鏃ユ湡" required>
                        <el-date-picker
                          v-model="form.end_date"
                          type="date"
                          placeholder="閫夋嫨缁撴潫鏃ユ湡"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- 鑲＄エ閫夋嫨 -->
                  <el-form-item label="鑲＄エ閫夋嫨">
                    <el-radio-group v-model="form.collection_type">
                      <el-radio value="single">鍗曚釜鑲＄エ閲囬泦</el-radio>
                      <el-radio value="multiple">澶氫釜鑲＄エ閲囬泦</el-radio>
                      <el-radio value="all">鍏ㄩ噺鑲＄エ閲囬泦</el-radio>
                    </el-radio-group>
                  </el-form-item>

                  <!-- 鍗曚釜鑲＄エ浠ｇ爜杈撳叆 -->
                  <el-form-item v-if="form.collection_type === 'single'" label="鑲＄エ浠ｇ爜" required>
                    <el-input
                      v-model="form.single_stock_code"
                      placeholder="请输入股票代码，例如：000001"
                      clearable
                    />
                    <div class="text-sm text-gray-500 mt-1">鏀寔杈撳叆鍗曚釜鑲＄エ浠ｇ爜杩涜閲囬泦</div>
                  </el-form-item>

                  <!-- 澶氫釜鑲＄エ浠ｇ爜杈撳叆 -->
                  <el-form-item v-if="form.collection_type === 'multiple'" label="鑲＄エ浠ｇ爜" required>
                    <el-input
                      v-model="form.stock_codes_text"
                      type="textarea"
                      :rows="5"
                      placeholder="请输入股票代码，每行一个，例如：&#10;000001&#10;000002&#10;000858"
                    />
                    <div class="text-sm text-gray-500 mt-1">鏀寔杈撳叆澶氫釜鑲＄エ浠ｇ爜锛屾瘡琛屼竴涓?/div>
                  </el-form-item>

                  <!-- 鍏ㄩ噺閲囬泦璇存槑 -->
                  <el-alert
                    v-if="form.collection_type === 'all'"
                    title="鍏ㄩ噺閲囬泦璇存槑"
                    type="info"
                    :closable="false"
                    show-icon
                  >
                    <p>灏嗛噰闆嗘暟鎹簱涓墍鏈夎偂绁ㄧ殑鍘嗗彶鏁版嵁銆傜敱浜巃kshare闄愭祦瑕佹眰锛岀郴缁熼噰鐢ㄥ崟浠诲姟鎵ц妯″紡锛?
                    宸查噰闆嗚繃鐨勮偂绁ㄦ暟鎹皢琚烦杩囷紝閬垮厤閲嶅閲囬泦銆?/p>
                  </el-alert>

                  <!-- 娴嬭瘯妯″紡 -->
                  <el-form-item>
                    <el-checkbox v-model="form.test_mode">娴嬭瘯妯″紡锛堝彧閲囬泦鍓?鍙偂绁級</el-checkbox>
                  </el-form-item>

                  <!-- 鎿嶄綔鎸夐挳 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="loading"
                      :disabled="!!currentTask"
                      @click="startCollection"
                    >
                      <el-icon v-if="loading" class="mr-2"><Loading /></el-icon>
                      {{ loading ? '鍚姩涓?..' : (currentTask ? '绛夊緟褰撳墠浠诲姟瀹屾垚' : '寮€濮嬮噰闆?) }}
                    </el-button>
                    <el-button @click="resetForm">閲嶇疆</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-card>
          </el-tab-pane>

          <!-- TuShare鏍囩椤?-->
          <el-tab-pane label="鍘嗗彶鏁版嵁閲囬泦-TuShare" name="tushare">
            <el-card>
              <div class="text-center mb-8">
                <el-icon class="text-6xl text-gray-400 mb-4"><DataAnalysis /></el-icon>
                <h2 class="text-2xl font-bold text-gray-900 mb-2">鍘嗗彶鏁版嵁閲囬泦-TuShare</h2>
                <p class="text-gray-600">浣跨敤tushare閲囬泦A鑲″叏閲忓巻鍙茶鎯呮暟鎹?/p>
              </div>

              <!-- TuShare閲囬泦閰嶇疆琛ㄥ崟 -->
              <div class="max-w-2xl mx-auto">
                <el-form @submit.prevent="startTushareCollection" :model="tushareForm" label-width="120px">
                  <!-- 鏃ユ湡鑼冨洿 -->
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="寮€濮嬫棩鏈? required>
                        <el-date-picker
                          v-model="tushareForm.start_date"
                          type="date"
                          placeholder="閫夋嫨寮€濮嬫棩鏈?
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="缁撴潫鏃ユ湡" required>
                        <el-date-picker
                          v-model="tushareForm.end_date"
                          type="date"
                          placeholder="閫夋嫨缁撴潫鏃ユ湡"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- 寮哄埗鏇存柊閫夐」 -->
                  <el-form-item>
                    <el-checkbox v-model="tushareForm.force_update">
                      寮哄埗鏇存柊锛堝鏋滃凡瀛樺湪姝ゆ棩鏈熺殑鍘嗗彶鏁版嵁锛屽皢鍏堝垹闄ゅ悗鎻掑叆锛?
                    </el-checkbox>
                    <div class="text-sm text-gray-500 mt-1">
                      鏈€夋嫨寮哄埗鏇存柊鏃讹紝濡傛灉宸插瓨鍦ㄦ暟鎹垯璺宠繃鎻掑叆
                    </div>
                  </el-form-item>

                  <!-- 鎿嶄綔鎸夐挳 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="tushareLoading"
                      :disabled="!!currentTask"
                      @click="startTushareCollection"
                    >
                      <el-icon v-if="tushareLoading" class="mr-2"><Loading /></el-icon>
                      {{ tushareLoading ? '鍚姩涓?..' : (currentTask ? '绛夊緟褰撳墠浠诲姟瀹屾垚' : '寮€濮嬮噰闆?) }}
                    </el-button>
                    <el-button @click="resetTushareForm">閲嶇疆</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>

      <!-- 娓偂鍘嗗彶鏁版嵁閲囬泦 -->
      <el-tab-pane label="娓偂鍘嗗彶鏁版嵁閲囬泦" name="hkshare">
        <el-tabs v-model="activeHKShareTab">
          <el-tab-pane label="娓偂鍘嗗彶鏁版嵁閲囬泦-AkShare" name="hk_akshare">
            <el-card>
              <div class="text-center mb-8">
                <el-icon class="text-6xl text-gray-400 mb-4"><DataAnalysis /></el-icon>
                <h2 class="text-2xl font-bold text-gray-900 mb-2">娓偂鍘嗗彶鏁版嵁閲囬泦-AkShare</h2>
                <p class="text-gray-600">浣跨敤akshare閲囬泦娓偂鍘嗗彶琛屾儏鏁版嵁</p>
              </div>

              <div class="max-w-2xl mx-auto">
                <el-form @submit.prevent="startHKCollection" :model="hkForm" label-width="120px">
                  <!-- 鏃ユ湡鑼冨洿 -->
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="寮€濮嬫棩鏈? required>
                        <el-date-picker
                          v-model="hkForm.start_date"
                          type="date"
                          placeholder="閫夋嫨寮€濮嬫棩鏈?
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="缁撴潫鏃ユ湡" required>
                        <el-date-picker
                          v-model="hkForm.end_date"
                          type="date"
                          placeholder="閫夋嫨缁撴潫鏃ユ湡"
                          format="YYYY-MM-DD"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- 閲囬泦绫诲瀷 -->
                  <el-form-item label="閲囬泦绫诲瀷" required>
                    <el-radio-group v-model="hkForm.collection_type">
                      <el-radio label="specified">鎸囧畾鑲＄エ</el-radio>
                      <el-radio label="all">鍏ㄩ噺閲囬泦</el-radio>
                    </el-radio-group>
                  </el-form-item>

                  <!-- 娓偂浠ｇ爜 -->
                  <el-form-item label="娓偂浠ｇ爜" required v-if="hkForm.collection_type === 'specified'">
                    <el-input
                      v-model="hkForm.stock_codes_text"
                      type="textarea"
                      :rows="5"
                      placeholder="璇疯緭鍏ユ腐鑲′唬鐮侊紙5浣嶆暟瀛楋級锛屾瘡琛屼竴涓紝渚嬪锛?#10;00700&#10;09988"
                    />
                    <div class="text-sm text-gray-500 mt-1">璇疯緭鍏ラ渶瑕侀噰闆嗙殑娓偂浠ｇ爜</div>
                  </el-form-item>

                  <!-- 鍏ㄩ噺閲囬泦璇存槑 -->
                  <el-alert
                    v-if="hkForm.collection_type === 'all'"
                    title="鍏ㄩ噺閲囬泦璇存槑"
                    type="info"
                    :closable="false"
                    show-icon
                    class="mb-4"
                  >
                    <p>灏嗛噰闆嗘暟鎹簱涓墍鏈夋腐鑲＄殑鍘嗗彶鏁版嵁銆傜敱浜巃kshare闄愭祦瑕佹眰锛岀郴缁熼噰鐢ㄥ崟浠诲姟鎵ц妯″紡锛屾瘡娆￠噰闆嗛棿闅?绉掋€?/p>
                  </el-alert>

                  <!-- 寮哄埗鏇存柊閫夐」 -->
                  <el-form-item>
                    <el-checkbox v-model="hkForm.force_update">
                      寮哄埗鏇存柊锛堝鏋滃凡瀛樺湪姝ゆ棩鏈熺殑鍘嗗彶鏁版嵁锛屽皢閲嶆柊閲囬泦骞舵洿鏂帮級
                    </el-checkbox>
                    <div class="text-sm text-gray-500 mt-1">
                      鏈€夋嫨寮哄埗鏇存柊鏃讹紝濡傛灉宸插瓨鍦ㄦ暟鎹垯璺宠繃鎻掑叆
                    </div>
                  </el-form-item>

                  <!-- 鎿嶄綔鎸夐挳 -->
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="hkLoading"
                      :disabled="!!currentTask"
                      @click="startHKCollection"
                    >
                      <el-icon v-if="hkLoading" class="mr-2"><Loading /></el-icon>
                      {{ hkLoading ? '鍚姩涓?..' : (currentTask ? '绛夊緟褰撳墠浠诲姟瀹屾垚' : '寮€濮嬮噰闆?) }}
                    </el-button>
                    <el-button @click="resetHKForm">閲嶇疆</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>
    </el-tabs>

    <!-- 浠诲姟鍒楄〃 -->
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span>閲囬泦浠诲姟</span>
          <el-button type="text" @click="loadTasks" :icon="Refresh">
            鍒锋柊
          </el-button>
        </div>
      </template>

      <div v-if="tasks.length === 0" class="text-center text-gray-500 py-8">
        鏆傛棤閲囬泦浠诲姟
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
              <h4 class="font-medium text-gray-900">浠诲姟 {{ task.task_id }}</h4>
              <p class="text-sm text-gray-500">
                {{ formatTime(task.start_time) }} - {{ task.end_time ? formatTime(task.end_time) : '杩涜涓? }}
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
                鍙栨秷
              </el-button>
            </div>
          </div>
          
          <!-- 杩涘害鏉?-->
          <div v-if="task.status === 'running'" class="mb-3">
            <div class="flex justify-between text-sm text-gray-600 mb-1">
              <span>杩涘害</span>
              <span>{{ task.progress }}%</span>
            </div>
            <el-progress :percentage="task.progress" />
          </div>

          <!-- 缁熻淇℃伅 -->
          <el-row :gutter="20" class="text-sm">
            <el-col :span="6">
              <span class="text-gray-500">鎬昏偂绁ㄦ暟:</span>
              <span class="font-medium">{{ task.total_stocks }}</span>
            </el-col>
            <el-col :span="6">
              <span class="text-gray-500">鎴愬姛:</span>
              <span class="font-medium text-green-600">{{ task.success_count }}</span>
            </el-col>
            <el-col :span="6">
              <span class="text-gray-500">澶辫触:</span>
              <span class="font-medium text-red-600">{{ task.failed_count }}</span>
            </el-col>
            <el-col :span="6">
              <span class="text-gray-500">鏂板鏁版嵁:</span>
              <span class="font-medium text-blue-600">{{ task.collected_count }}</span>
            </el-col>
          </el-row>

          <!-- 閿欒淇℃伅 -->
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
import { ref, onMounted, onUnmounted } from 'vue'
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

// 绫诲瀷瀹氫箟
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
}

interface HKFormData {
  start_date: string
  end_date: string
  stock_codes_text: string
  collection_type: 'specified' | 'all'
  force_update: boolean
}

interface RequestData {
  start_date: string
  end_date: string
  test_mode: boolean
  stock_codes?: string[]
  full_collection_mode?: boolean
  market?: string
  force_update?: boolean
}

// 鏍囩椤电姸鎬?
const activeMainTab = ref('ashare')
const activeAShareTab = ref('akshare')
const activeHKShareTab = ref('hk_akshare')

// 琛ㄥ崟鏁版嵁
const form = ref<FormData>({
  start_date: '',
  end_date: '',
  collection_type: 'single',
  single_stock_code: '',
  stock_codes_text: '',
  test_mode: false
})

// HK琛ㄥ崟鏁版嵁
const hkForm = ref<HKFormData>({
  start_date: '',
  end_date: '',
  stock_codes_text: '',
  collection_type: 'specified',
  force_update: false
})

// TuShare琛ㄥ崟鏁版嵁
interface TushareFormData {
  start_date: string
  end_date: string
  force_update: boolean
}

const tushareForm = ref<TushareFormData>({
  start_date: '',
  end_date: '',
  force_update: false
})

// 鐘舵€佹暟鎹?
const tasks = ref<Task[]>([])
const currentTask = ref<CurrentTask | null>(null)
const loading = ref(false)
const hkLoading = ref(false)
const tushareLoading = ref(false)
const pollingInterval = ref<NodeJS.Timeout | null>(null)

// 鏂规硶
const startCollection = async () => {
  try {
    loading.value = true
    
    // 楠岃瘉琛ㄥ崟
    if (!form.value.start_date || !form.value.end_date) {
      ElMessage.error('请选择开始日期和结束日期')
      return
    }
    
    // 妫€鏌ュ綋鍓嶄换鍔＄姸鎬?
    if (currentTask.value) {
      ElMessage.error('已有数据收集任务正在运行，请等待完成后再启动新任务')
      return
    }
    
    // 准备请求数据
    const requestData: RequestData = {
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      test_mode: form.value.test_mode
    }

    // 根据收集类型设置股票代码
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
      // 鍏ㄩ噺閲囬泦妯″紡
      requestData.full_collection_mode = true
    }

    console.log('鍙戦€佽姹?', requestData)
    const response = await axios.post(`${API_BASE}/api/data-collection/historical`, requestData)
    
    if (response.data.status === 'started') {
      ElMessage.success('收集任务已启动')
      loadTasks()
      loadCurrentTask()
    }
    
  } catch (error: any) {
    console.error('鍚姩閲囬泦浠诲姟澶辫触:', error)
    let errorMsg = '鍚姩閲囬泦浠诲姟澶辫触'
    
    if (error.response) {
      // 鏈嶅姟鍣ㄥ搷搴斾簡閿欒鐘舵€佺爜
      errorMsg = error.response.data?.detail || `鏈嶅姟鍣ㄩ敊璇?(${error.response.status})`
    } else if (error.request) {
      // 璇锋眰宸插彂鍑轰絾娌℃湁鏀跺埌鍝嶅簲
      errorMsg = '无法连接到服务器，请检查网络连接'
    } else {
      // 鍏朵粬閿欒
      errorMsg = error.message || '鏈煡閿欒'
    }
    
    ElMessage.error(errorMsg)
  } finally {
    loading.value = false
  }
}

const startHKCollection = async () => {
  try {
    hkLoading.value = true
    
    // 楠岃瘉琛ㄥ崟
    if (!hkForm.value.start_date || !hkForm.value.end_date) {
      ElMessage.error('请选择开始日期和结束日期')
      return
    }

    if (hkForm.value.collection_type === 'specified' && !hkForm.value.stock_codes_text.trim()) {
      ElMessage.error('请输入港股代码')
      return
    }
    
    // 妫€鏌ュ綋鍓嶄换鍔＄姸鎬?
    if (currentTask.value) {
      ElMessage.error('已有数据收集任务正在运行，请等待完成后再启动新任务')
      return
    }
    
    // 鍑嗗璇锋眰鏁版嵁
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
    } else {
      requestData.full_collection_mode = true
    }

    console.log('鍙戦€佹腐鑲￠噰闆嗚姹?', requestData)
    const response = await axios.post(`${API_BASE}/api/data-collection/historical`, requestData)
    
    if (response.data.status === 'started') {
      ElMessage.success('港股收集任务已启动')
      loadTasks()
      loadCurrentTask()
    }
    
  } catch (error: any) {
    console.error('鍚姩娓偂閲囬泦浠诲姟澶辫触:', error)
    let errorMsg = '鍚姩娓偂閲囬泦浠诲姟澶辫触'
    
    if (error.response) {
      errorMsg = error.response.data?.detail || `鏈嶅姟鍣ㄩ敊璇?(${error.response.status})`
    } else if (error.request) {
      errorMsg = '无法连接到服务器，请检查网络连接'
    } else {
      errorMsg = error.message || '鏈煡閿欒'
    }
    
    ElMessage.error(errorMsg)
  } finally {
    hkLoading.value = false
  }
}

const loadTasks = async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/data-collection/tasks`)
    tasks.value = response.data
  } catch (error) {
    console.error('鍔犺浇浠诲姟鍒楄〃澶辫触:', error)
  }
}

const loadCurrentTask = async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/data-collection/current-task`)
    currentTask.value = response.data.current_task
  } catch (error) {
    console.error('鍔犺浇褰撳墠浠诲姟淇℃伅澶辫触:', error)
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
      console.error('鍙栨秷浠诲姟澶辫触:', error)
      ElMessage.error(error.response?.data?.detail || '鍙栨秷浠诲姟澶辫触')
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
    test_mode: false
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

const resetTushareForm = () => {
  tushareForm.value = {
    start_date: '',
    end_date: '',
    force_update: false
  }
}

const startTushareCollection = async () => {
  try {
    tushareLoading.value = true
    
    // 楠岃瘉琛ㄥ崟
    if (!tushareForm.value.start_date || !tushareForm.value.end_date) {
      ElMessage.error('请选择开始日期和结束日期')
      return
    }
    
    // 妫€鏌ュ綋鍓嶄换鍔＄姸鎬?
    if (currentTask.value) {
      ElMessage.error('已有数据收集任务正在运行，请等待完成后再启动新任务')
      return
    }

    console.log('鍙戦€乀uShare閲囬泦璇锋眰:', tushareForm.value)
    const response = await axios.post(`${API_BASE}/api/data-collection/tushare-historical`, {
      start_date: tushareForm.value.start_date,
      end_date: tushareForm.value.end_date,
      force_update: tushareForm.value.force_update
    })
    
    if (response.data.status === 'started') {
      ElMessage.success('TuShare收集任务已启动')
      loadTasks()
      loadCurrentTask()
    }
    
  } catch (error: any) {
    console.error('鍚姩TuShare閲囬泦浠诲姟澶辫触:', error)
    let errorMsg = '鍚姩TuShare閲囬泦浠诲姟澶辫触'
    
    if (error.response) {
      errorMsg = error.response.data?.detail || `鏈嶅姟鍣ㄩ敊璇?(${error.response.status})`
    } else if (error.request) {
      errorMsg = '无法连接到服务器，请检查网络连接'
    } else {
      errorMsg = error.message || '鏈煡閿欒'
    }
    
    ElMessage.error(errorMsg)
  } finally {
    tushareLoading.value = false
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
  }, 5000) // 姣?绉掑埛鏂颁竴娆?
}

const stopPolling = () => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
}

// 鐢熷懡鍛ㄦ湡
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
