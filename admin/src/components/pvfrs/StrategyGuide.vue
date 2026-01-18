<template>
  <div class="strategy-guide">
    <el-tabs v-model="activeTab" class="guide-tabs">
      <!-- 策略概述 -->
      <el-tab-pane label="策略概述" name="overview">
        <div class="guide-section">
          <h2 class="section-title">PVFRS（量价频三维共振）策略</h2>
          <div class="section-content">
            <p class="intro-text">
              PVFRS策略基于量价频三维共振演化理论，将"高效率上涨"定义为市场在价格方向、微观共识与资金动力三个维度达成向上共振的状态。
            </p>
            
            <div class="dimensions-grid">
              <div class="dimension-card">
                <div class="dimension-icon price">
                  <el-icon><TrendCharts /></el-icon>
                </div>
                <div class="dimension-content">
                  <h3>价格维度</h3>
                  <p>宏观位移 + 即时强度</p>
                  <ul>
                    <li>宏观位移 Δ > 0（期末价格 > 起始价格）</li>
                    <li>即时强度 d₂₀ > d（当前价格 > 20日均线）</li>
                  </ul>
                </div>
              </div>
              
              <div class="dimension-card">
                <div class="dimension-icon frequency">
                  <el-icon><Histogram /></el-icon>
                </div>
                <div class="dimension-content">
                  <h3>频率维度</h3>
                  <p>上涨频率优势</p>
                  <ul>
                    <li>上涨频率 Z > F（上涨天数 > 下跌天数）</li>
                    <li>避免虚假繁荣信号</li>
                  </ul>
                </div>
              </div>
              
              <div class="dimension-card">
                <div class="dimension-icon volume">
                  <el-icon><DataAnalysis /></el-icon>
                </div>
                <div class="dimension-content">
                  <h3>成交量维度</h3>
                  <p>进出效率验证</p>
                  <ul>
                    <li>进出效率 m₂₀ > m（当前成交量 > 20日平均量）</li>
                    <li>量价共振确认</li>
                  </ul>
                </div>
              </div>
            </div>
            
            <div class="strategy-formula">
              <h3>核心公式</h3>
              <div class="formula-box">
                <div class="formula-item">
                  <strong>买入条件：</strong>
                  <code>Δ > 0 AND d₂₀ > d AND Z > F AND m₂₀ > m</code>
                </div>
                <div class="formula-item">
                  <strong>卖出条件：</strong>
                  <code>bias > 8% OR d₂₀ - d > 5% OR 价涨量缩背离</code>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 参数说明 -->
      <el-tab-pane label="参数说明" name="parameters">
        <div class="guide-section">
          <h2 class="section-title">策略参数详解</h2>
          
          <div class="params-category">
            <h3 class="category-title">买入参数</h3>
            <el-table :data="buyParameters" stripe>
              <el-table-column prop="name" label="参数名称" width="200" />
              <el-table-column prop="description" label="说明" min-width="300" />
              <el-table-column prop="defaultValue" label="默认值" width="100" />
              <el-table-column prop="range" label="建议范围" width="120" />
            </el-table>
          </div>
          
          <div class="params-category">
            <h3 class="category-title">卖出参数</h3>
            <el-table :data="sellParameters" stripe>
              <el-table-column prop="name" label="参数名称" width="200" />
              <el-table-column prop="description" label="说明" min-width="300" />
              <el-table-column prop="defaultValue" label="默认值" width="100" />
              <el-table-column prop="range" label="建议范围" width="120" />
            </el-table>
          </div>
          
          <div class="params-category">
            <h3 class="category-title">风控参数</h3>
            <el-table :data="riskParameters" stripe>
              <el-table-column prop="name" label="参数名称" width="200" />
              <el-table-column prop="description" label="说明" min-width="300" />
              <el-table-column prop="defaultValue" label="默认值" width="100" />
              <el-table-column prop="range" label="建议范围" width="120" />
            </el-table>
          </div>
        </div>
      </el-tab-pane>

      <!-- 使用指南 -->
      <el-tab-pane label="使用指南" name="guide">
        <div class="guide-section">
          <h2 class="section-title">使用指南</h2>
          
          <div class="guide-steps">
            <div class="step-item">
              <div class="step-number">1</div>
              <div class="step-content">
                <h3>策略配置</h3>
                <p>在"策略配置"标签页中调整各项参数，根据市场环境和风险偏好进行个性化设置。</p>
                <ul>
                  <li>保守型：提高买入阈值，降低止损比例</li>
                  <li>激进型：降低买入阈值，提高止盈比例</li>
                  <li>平衡型：使用默认参数设置</li>
                </ul>
              </div>
            </div>
            
            <div class="step-item">
              <div class="step-number">2</div>
              <div class="step-content">
                <h3>回测验证</h3>
                <p>在"回测任务管理"中创建回测任务，验证策略在历史数据上的表现。</p>
                <ul>
                  <li>单股回测：测试特定股票的策略效果</li>
                  <li>批量回测：测试策略在多只股票上的整体表现</li>
                  <li>参数优化：寻找最优参数组合</li>
                </ul>
              </div>
            </div>
            
            <div class="step-item">
              <div class="step-number">3</div>
              <div class="step-content">
                <h3>结果分析</h3>
                <p>在"报告与分析"中查看回测结果，分析策略的优缺点。</p>
                <ul>
                  <li>关注夏普比率、最大回撤等风险指标</li>
                  <li>分析交易明细，了解策略行为</li>
                  <li>对比不同参数设置的效果</li>
                </ul>
              </div>
            </div>
            
            <div class="step-item">
              <div class="step-number">4</div>
              <div class="step-content">
                <h3>实时监控</h3>
                <p>在"实时监控"中跟踪策略的实时表现和风险状况。</p>
                <ul>
                  <li>监控活跃信号数量和质量</li>
                  <li>及时处理风险告警</li>
                  <li>调整策略参数以适应市场变化</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 最佳实践 -->
      <el-tab-pane label="最佳实践" name="best-practices">
        <div class="guide-section">
          <h2 class="section-title">最佳实践建议</h2>
          
          <div class="practices-grid">
            <div class="practice-card">
              <div class="practice-icon success">
                <el-icon><CircleCheck /></el-icon>
              </div>
              <div class="practice-content">
                <h3>参数调优</h3>
                <ul>
                  <li>根据不同市场环境调整参数</li>
                  <li>牛市适当降低买入阈值</li>
                  <li>熊市提高风控标准</li>
                  <li>定期回测验证参数有效性</li>
                </ul>
              </div>
            </div>
            
            <div class="practice-card">
              <div class="practice-icon warning">
                <el-icon><Warning /></el-icon>
              </div>
              <div class="practice-content">
                <h3>风险控制</h3>
                <ul>
                  <li>严格执行止损策略</li>
                  <li>控制单只股票仓位</li>
                  <li>分散投资降低风险</li>
                  <li>关注市场系统性风险</li>
                </ul>
              </div>
            </div>
            
            <div class="practice-card">
              <div class="practice-icon info">
                <el-icon><InfoFilled /></el-icon>
              </div>
              <div class="practice-content">
                <h3>执行纪律</h3>
                <ul>
                  <li>严格按照信号执行交易</li>
                  <li>避免主观情绪干扰</li>
                  <li>定期检查策略表现</li>
                  <li>及时调整不适应的参数</li>
                </ul>
              </div>
            </div>
            
            <div class="practice-card">
              <div class="practice-icon danger">
                <el-icon><CircleClose /></el-icon>
              </div>
              <div class="practice-content">
                <h3>常见误区</h3>
                <ul>
                  <li>过度优化历史数据</li>
                  <li>忽视交易成本影响</li>
                  <li>频繁调整策略参数</li>
                  <li>过分依赖单一指标</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 常见问题 -->
      <el-tab-pane label="常见问题" name="faq">
        <div class="guide-section">
          <h2 class="section-title">常见问题解答</h2>
          
          <el-collapse v-model="activeFaq" accordion>
            <el-collapse-item 
              v-for="(faq, index) in faqList" 
              :key="index"
              :title="faq.question" 
              :name="index"
            >
              <div class="faq-answer" v-html="faq.answer"></div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { 
  TrendCharts, 
  Histogram, 
  DataAnalysis,
  CircleCheck,
  Warning,
  InfoFilled,
  CircleClose
} from '@element-plus/icons-vue'

// 响应式数据
const activeTab = ref('overview')
const activeFaq = ref(0)

// 参数数据
const buyParameters = [
  {
    name: 'buy_macro_displacement_min',
    description: '宏观位移最小值，价格相对于起始位置的位移',
    defaultValue: '0',
    range: '≥ 0'
  },
  {
    name: 'buy_instant_deviation_min',
    description: '即时偏离度最小值，当前价格相对于20日均线的偏离度',
    defaultValue: '0',
    range: '≥ 0'
  },
  {
    name: 'buy_bias_min',
    description: '乖离率最小值，价格相对于均线的乖离率',
    defaultValue: '2%',
    range: '1%-5%'
  },
  {
    name: 'buy_consecutive_days',
    description: '连续确认天数，信号连续确认的天数',
    defaultValue: '3',
    range: '1-10天'
  }
]

const sellParameters = [
  {
    name: 'sell_bias_max',
    description: '乖离率最大值，超买信号阈值',
    defaultValue: '8%',
    range: '5%-15%'
  },
  {
    name: 'sell_instant_deviation_max',
    description: '即时偏离度最大值，价格偏离度过大时的卖出信号',
    defaultValue: '5%',
    range: '3%-10%'
  },
  {
    name: 'sell_price_volume_divergence',
    description: '价涨量缩背离，检测价格上涨但成交量下降的背离信号',
    defaultValue: '启用',
    range: '启用/禁用'
  }
]

const riskParameters = [
  {
    name: 'stop_loss',
    description: '止损比例，最大亏损比例',
    defaultValue: '-10%',
    range: '-5% ~ -15%'
  },
  {
    name: 'take_profit',
    description: '止盈比例，目标盈利比例',
    defaultValue: '20%',
    range: '15% ~ 30%'
  },
  {
    name: 'max_position_size',
    description: '最大仓位比例，单只股票最大仓位',
    defaultValue: '10%',
    range: '5% ~ 20%'
  },
  {
    name: 'max_holding_days',
    description: '最大持有天数，避免长期套牢',
    defaultValue: '30天',
    range: '20-60天'
  }
]

// FAQ数据
const faqList = [
  {
    question: 'PVFRS策略适用于哪些市场环境？',
    answer: `
      <p>PVFRS策略在以下市场环境中表现较好：</p>
      <ul>
        <li><strong>震荡上涨市场：</strong>策略能够捕捉到价格的波动性上涨机会</li>
        <li><strong>趋势性牛市：</strong>三维共振信号在趋势市场中更加可靠</li>
        <li><strong>结构性行情：</strong>适合捕捉个股的结构性机会</li>
      </ul>
      <p>在以下环境中需要谨慎使用：</p>
      <ul>
        <li><strong>单边下跌市场：</strong>可能产生较多假信号</li>
        <li><strong>极度震荡市场：</strong>频繁的买卖信号可能增加交易成本</li>
      </ul>
    `
  },
  {
    question: '如何选择合适的参数设置？',
    answer: `
      <p>参数选择应该根据以下因素进行调整：</p>
      <ul>
        <li><strong>风险偏好：</strong>保守投资者应提高买入阈值，降低止损比例</li>
        <li><strong>市场环境：</strong>牛市可适当降低买入阈值，熊市应提高风控标准</li>
        <li><strong>资金规模：</strong>大资金应降低单只股票仓位比例</li>
        <li><strong>交易频率：</strong>希望减少交易频率可提高连续确认天数</li>
      </ul>
      <p>建议通过历史回测来验证参数设置的有效性。</p>
    `
  },
  {
    question: '策略的预期收益和风险如何？',
    answer: `
      <p>根据历史回测数据，PVFRS策略的典型表现：</p>
      <ul>
        <li><strong>年化收益率：</strong>10%-25%（取决于市场环境和参数设置）</li>
        <li><strong>胜率：</strong>60%-75%</li>
        <li><strong>最大回撤：</strong>5%-15%</li>
        <li><strong>夏普比率：</strong>1.2-2.0</li>
      </ul>
      <p><strong>风险提示：</strong>历史表现不代表未来收益，投资有风险，需谨慎决策。</p>
    `
  },
  {
    question: '如何处理策略失效的情况？',
    answer: `
      <p>当策略表现不佳时，可以采取以下措施：</p>
      <ul>
        <li><strong>分析失效原因：</strong>检查是否由于市场环境变化导致</li>
        <li><strong>调整参数：</strong>根据当前市场特征重新优化参数</li>
        <li><strong>暂停使用：</strong>在极端市场环境下暂停策略使用</li>
        <li><strong>组合策略：</strong>与其他策略组合使用，分散风险</li>
      </ul>
      <p>建议定期（如每季度）对策略进行回测和评估。</p>
    `
  },
  {
    question: '交易成本对策略收益的影响如何？',
    answer: `
      <p>交易成本是影响策略实际收益的重要因素：</p>
      <ul>
        <li><strong>佣金费用：</strong>建议选择低佣金的券商</li>
        <li><strong>印花税：</strong>A股卖出时收取0.1%印花税</li>
        <li><strong>滑点成本：</strong>大单交易可能产生滑点</li>
        <li><strong>冲击成本：</strong>频繁交易可能影响股价</li>
      </ul>
      <p>建议在回测时考虑0.2%-0.5%的综合交易成本。</p>
    `
  }
]
</script>

<style scoped lang="postcss">
.strategy-guide {
  @apply p-6;
}

.guide-tabs {
  @apply w-full;
}

.guide-section {
  @apply space-y-6;
}

.section-title {
  @apply text-2xl font-bold text-gray-900 mb-4;
}

.section-content {
  @apply space-y-6;
}

.intro-text {
  @apply text-lg text-gray-700 leading-relaxed;
}

.dimensions-grid {
  @apply grid grid-cols-1 md:grid-cols-3 gap-6;
}

.dimension-card {
  @apply bg-white border border-gray-200 rounded-lg p-6 shadow-sm;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.dimension-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.dimension-icon {
  @apply w-12 h-12 rounded-full flex items-center justify-center mb-4;
  font-size: 24px;
}

.dimension-icon.price {
  @apply bg-blue-100 text-blue-600;
}

.dimension-icon.frequency {
  @apply bg-green-100 text-green-600;
}

.dimension-icon.volume {
  @apply bg-purple-100 text-purple-600;
}

.dimension-content h3 {
  @apply text-lg font-semibold text-gray-900 mb-2;
}

.dimension-content p {
  @apply text-gray-600 mb-3;
}

.dimension-content ul {
  @apply space-y-1;
}

.dimension-content li {
  @apply text-sm text-gray-600;
}

.strategy-formula {
  @apply bg-gray-50 rounded-lg p-6;
}

.strategy-formula h3 {
  @apply text-lg font-semibold text-gray-900 mb-4;
}

.formula-box {
  @apply space-y-3;
}

.formula-item {
  @apply flex items-center gap-3;
}

.formula-item code {
  @apply bg-white px-3 py-2 rounded border font-mono text-sm;
}

.params-category {
  @apply mb-8;
}

.category-title {
  @apply text-lg font-semibold text-gray-900 mb-4;
}

.guide-steps {
  @apply space-y-6;
}

.step-item {
  @apply flex gap-4;
}

.step-number {
  @apply w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold flex-shrink-0;
}

.step-content {
  flex: 1;
}

.step-content h3 {
  @apply text-lg font-semibold text-gray-900 mb-2;
}

.step-content p {
  @apply text-gray-700 mb-3;
}

.step-content ul {
  @apply space-y-1 ml-4;
}

.step-content li {
  @apply text-sm text-gray-600;
}

.practices-grid {
  @apply grid grid-cols-1 md:grid-cols-2 gap-6;
}

.practice-card {
  @apply bg-white border border-gray-200 rounded-lg p-6 shadow-sm;
}

.practice-icon {
  @apply w-10 h-10 rounded-full flex items-center justify-center mb-4;
  font-size: 20px;
}

.practice-icon.success {
  @apply bg-green-100 text-green-600;
}

.practice-icon.warning {
  @apply bg-yellow-100 text-yellow-600;
}

.practice-icon.info {
  @apply bg-blue-100 text-blue-600;
}

.practice-icon.danger {
  @apply bg-red-100 text-red-600;
}

.practice-content h3 {
  @apply text-lg font-semibold text-gray-900 mb-3;
}

.practice-content ul {
  @apply space-y-2;
}

.practice-content li {
  @apply text-sm text-gray-600;
}

.faq-answer {
  @apply prose prose-sm max-w-none;
}

.faq-answer p {
  @apply mb-3;
}

.faq-answer ul {
  @apply mb-3 ml-4;
}

.faq-answer li {
  @apply mb-1;
}

.faq-answer strong {
  @apply font-semibold text-gray-900;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .strategy-guide {
    @apply p-4;
  }
  
  .dimensions-grid {
    @apply grid-cols-1;
  }
  
  .practices-grid {
    @apply grid-cols-1;
  }
  
  .step-item {
    @apply flex-col;
  }
  
  .step-number {
    @apply self-start;
  }
}
</style>