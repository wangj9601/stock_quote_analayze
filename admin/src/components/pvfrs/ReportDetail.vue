<template>
  <div class="report-detail">
    
    <div class="loading-container" v-if="loading" style="min-height: 400px; display: flex; align-items: center; justify-content: center;">
      <el-loading 
        :loading="loading"
        text="加载中..."
      ></el-loading>
      <div style="margin-left: 20px;">
        <span>正在加载报告详情，请稍候...</span>
      </div>
    </div>
    
    <div v-else-if="error" class="error-container">
      <el-result
        icon="error"
        title="加载失败"
        :sub-title="error"
      >
        <template #extra>
          <el-button type="primary" @click="loadReport">重新加载</el-button>
        </template>
      </el-result>
    </div>
    
    <div v-else-if="report" class="report-content">
      <!-- 调试信息（开发环境） -->
      <div v-if="false" style="background: #f0f0f0; padding: 10px; margin-bottom: 20px; font-size: 12px;">
        <strong>调试信息:</strong>
        <pre>{{ JSON.stringify(report, null, 2) }}</pre>
      </div>
      <!-- 报告头部 -->
      <div class="report-header">
        <el-page-header @back="goBack" :title="report.title">
          <template #content>
            <div class="header-content">
              <h1>{{ report.title }}</h1>
              <div class="report-meta">
                <el-tag type="primary">{{ report.type }}</el-tag>
                <span class="date">{{ formatDate(report.created_at) }}</span>
              </div>
            </div>
          </template>
        </el-page-header>
      </div>
      
      <!-- 报告主体 -->
      <div class="report-body">
        <el-card class="report-card">
          <div class="report-summary">
            <div v-if="typeof report.summary === 'string'" v-html="report.summary"></div>
            <div v-else-if="typeof report.summary === 'object'" class="summary-object">
              <h4>摘要信息</h4>
              <div class="summary-content">
                <div v-if="report.summary.strategy_score !== undefined" class="summary-item">
                  <span class="label">策略评分:</span>
                  <span>{{ report.summary.strategy_score }}</span>
                </div>
                <div v-if="report.summary.strategy_grade !== undefined" class="summary-item">
                  <span class="label">策略等级:</span>
                  <span>{{ report.summary.strategy_grade }}</span>
                </div>
                <div v-if="report.summary.total_return !== undefined" class="summary-item">
                  <span class="label">总收益率:</span>
                  <span :class="report.summary.total_return >= 0 ? 'positive' : 'negative'">
                    {{ (report.summary.total_return * 100).toFixed(2) }}%
                  </span>
                </div>
                <div v-if="report.summary.annual_return !== undefined" class="summary-item">
                  <span class="label">年化收益率:</span>
                  <span :class="report.summary.annual_return >= 0 ? 'positive' : 'negative'">
                    {{ (report.summary.annual_return * 100).toFixed(2) }}%
                  </span>
                </div>
                <div v-if="report.summary.max_drawdown !== undefined" class="summary-item">
                  <span class="label">最大回撤:</span>
                  <span class="negative">{{ (report.summary.max_drawdown * 100).toFixed(2) }}%</span>
                </div>
                <div v-if="report.summary.sharpe_ratio !== undefined" class="summary-item">
                  <span class="label">夏普比率:</span>
                  <span>{{ report.summary.sharpe_ratio.toFixed(2) }}</span>
                </div>
                <div v-if="report.summary.win_rate !== undefined" class="summary-item">
                  <span class="label">胜率:</span>
                  <span>{{ (report.summary.win_rate * 100).toFixed(2) }}%</span>
                </div>
                <div v-if="report.summary.total_trades !== undefined" class="summary-item">
                  <span class="label">总交易次数:</span>
                  <span>{{ report.summary.total_trades }}</span>
                </div>
                <div v-if="report.summary.winning_trades !== undefined" class="summary-item">
                  <span class="label">盈利交易:</span>
                  <span>{{ report.summary.winning_trades }}</span>
                </div>
                <div v-if="report.summary.profit_factor !== undefined" class="summary-item">
                  <span class="label">盈利因子:</span>
                  <span>{{ report.summary.profit_factor.toFixed(2) }}</span>
                </div>
                
                <!-- 显示关键亮点 -->
                <div v-if="report.summary.key_highlights" class="summary-item full-width">
                  <span class="label">关键亮点:</span>
                  <div class="highlights">
                    <span v-for="(highlight, index) in report.summary.key_highlights" :key="index" class="highlight-tag">
                      {{ highlight }}
                    </span>
                  </div>
                </div>
                
                <!-- 显示风险警告 -->
                <div v-if="report.summary.risk_warnings" class="summary-item full-width">
                  <span class="label">风险警告:</span>
                  <div class="warnings">
                    <span v-for="(warning, index) in report.summary.risk_warnings" :key="index" class="warning-tag">
                      {{ warning }}
                    </span>
                  </div>
                </div>
                
                <!-- 显示建议 -->
                <div v-if="report.summary.recommendation" class="summary-item full-width">
                  <span class="label">投资建议:</span>
                  <span class="recommendation">{{ report.summary.recommendation }}</span>
                </div>
                
                <!-- 显示摘要文本 -->
                <div v-if="report.summary.summary_text" class="summary-item full-width">
                  <span class="label">摘要说明:</span>
                  <div class="summary-text" v-html="report.summary.summary_text"></div>
                </div>
              </div>
            </div>
            <div v-else class="summary-empty">
              <p>暂无摘要信息</p>
            </div>
          </div>
          
          <!-- 详细内容 -->
          <div class="report-details" v-if="report.details || report.visualization_data || report.comprehensive_data">
            <h3>详细分析</h3>
            <div v-if="report.details">
              <div v-if="typeof report.details === 'string'" v-html="report.details"></div>
              <div v-else-if="typeof report.details === 'object'" class="details-object">
                <h4>详细信息</h4>
                <pre>{{ JSON.stringify(report.details, null, 2) }}</pre>
              </div>
              <div v-else class="details-empty">
                <p>详细分析数据格式异常</p>
              </div>
            </div>
            <div v-else-if="report.visualization_data" class="visualization-analysis">
              <div class="analysis-section">
                <h4>📊 性能指标分析</h4>
                <div class="metrics-grid">
                  <div class="metric-item">
                    <span class="metric-label">总收益率</span>
                    <span class="metric-value" :class="report.visualization_data.performance_metrics.total_return >= 0 ? 'positive' : 'negative'">
                      {{ (report.visualization_data.performance_metrics.total_return * 100).toFixed(2) }}%
                    </span>
                  </div>
                  <div class="metric-item">
                    <span class="metric-label">年化收益率</span>
                    <span class="metric-value" :class="report.visualization_data.performance_metrics.annual_return >= 0 ? 'positive' : 'negative'">
                      {{ (report.visualization_data.performance_metrics.annual_return * 100).toFixed(2) }}%
                    </span>
                  </div>
                  <div class="metric-item">
                    <span class="metric-label">最大回撤</span>
                    <span class="metric-value negative">
                      {{ (report.visualization_data.performance_metrics.max_drawdown * 100).toFixed(2) }}%
                    </span>
                  </div>
                  <div class="metric-item">
                    <span class="metric-label">夏普比率</span>
                    <span class="metric-value">
                      {{ report.visualization_data.performance_metrics.sharpe_ratio.toFixed(2) }}
                    </span>
                  </div>
                  <div class="metric-item">
                    <span class="metric-label">波动率</span>
                    <span class="metric-value">
                      {{ (report.visualization_data.performance_metrics.volatility * 100).toFixed(2) }}%
                    </span>
                  </div>
                  <div class="metric-item">
                    <span class="metric-label">胜率</span>
                    <span class="metric-value">
                      {{ (report.visualization_data.performance_metrics.win_rate * 100).toFixed(2) }}%
                    </span>
                  </div>
                </div>
              </div>
              
              <div class="analysis-section">
                <h4>💰 交易分析</h4>
                <div class="trade-analysis">
                  <div class="trade-summary">
                    <div class="trade-stat">
                      <span class="stat-label">总交易次数</span>
                      <span class="stat-value">{{ report.visualization_data.trade_analysis.total_trades }}</span>
                    </div>
                    <div class="trade-stat">
                      <span class="stat-label">盈利交易</span>
                      <span class="stat-value positive">{{ report.visualization_data.trade_analysis.winning_trades }}</span>
                    </div>
                    <div class="trade-stat">
                      <span class="stat-label">亏损交易</span>
                      <span class="stat-value negative">{{ report.visualization_data.trade_analysis.losing_trades }}</span>
                    </div>
                    <div class="trade-stat">
                      <span class="stat-label">盈利因子</span>
                      <span class="stat-value">{{ report.visualization_data.trade_analysis.profit_factor.toFixed(2) }}</span>
                    </div>
                  </div>
                  
                  <div class="trade-distribution">
                    <h5>盈亏分布</h5>
                    <div class="distribution-stats">
                      <div class="dist-item">
                        <span class="dist-label">平均盈利</span>
                        <span class="dist-value positive">
                          ¥{{ report.visualization_data.trade_distribution.avg_win.toFixed(2) }}
                        </span>
                      </div>
                      <div class="dist-item">
                        <span class="dist-label">平均亏损</span>
                        <span class="dist-value negative">
                          ¥{{ report.visualization_data.trade_distribution.avg_loss.toFixed(2) }}
                        </span>
                      </div>
                      <div class="dist-item">
                        <span class="dist-label">平均持仓天数</span>
                        <span class="dist-value">
                          {{ report.visualization_data.trade_distribution.avg_holding_days.toFixed(1) }}天
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              <div class="analysis-section">
                <h4>📈 风险分析</h4>
                <div class="risk-analysis">
                  <div class="risk-metrics">
                    <div class="risk-item">
                      <span class="risk-label">最大连续亏损</span>
                      <span class="risk-value negative">
                        {{ report.visualization_data.risk_metrics.max_consecutive_losses }}次
                      </span>
                    </div>
                    <div class="risk-item">
                      <span class="risk-label">最大连续盈利</span>
                      <span class="risk-value positive">
                        {{ report.visualization_data.risk_metrics.max_consecutive_wins }}次
                      </span>
                    </div>
                    <div class="risk-item">
                      <span class="risk-label">VaR (95%)</span>
                      <span class="risk-value">
                        ¥{{ report.visualization_data.risk_metrics.var_95.toFixed(2) }}
                      </span>
                    </div>
                    <div class="risk-item">
                      <span class="risk-label">最大单日亏损</span>
                      <span class="risk-value negative">
                        ¥{{ report.visualization_data.risk_metrics.max_daily_loss.toFixed(2) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- 乖离率分析 -->
              <div v-if="report.visualization_data?.bias_analysis || report.comprehensive_data?.bias_analysis" class="analysis-section">
                <h4>📊 乖离率分析</h4>
                <div class="bias-analysis">
                  <div class="bias-metrics">
                    <div v-if="getBiasData('bias_quality_score') !== null" class="bias-item">
                      <span class="bias-label">Bias质量得分</span>
                      <span class="bias-value" :class="getBiasScoreClass(getBiasData('bias_quality_score'))">
                        {{ formatBiasScore(getBiasData('bias_quality_score')) }}
                      </span>
                    </div>
                    <div v-if="getBiasData('avg_bias') !== null" class="bias-item">
                      <span class="bias-label">平均乖离率</span>
                      <span class="bias-value" :class="getBiasValueClass(getBiasData('avg_bias'))">
                        {{ (getBiasData('avg_bias') * 100).toFixed(2) }}%
                      </span>
                    </div>
                    <div v-if="getBiasData('bias_trend_5d') !== null" class="bias-item">
                      <span class="bias-label">5天趋势</span>
                      <span class="bias-value" :class="getBiasTrendClass(getBiasData('bias_trend_5d'))">
                        {{ getBiasTrendLabel(getBiasData('bias_trend_5d')) }}
                      </span>
                    </div>
                    <div v-if="getBiasData('bias_trend_10d') !== null" class="bias-item">
                      <span class="bias-label">10天趋势</span>
                      <span class="bias-value" :class="getBiasTrendClass(getBiasData('bias_trend_10d'))">
                        {{ getBiasTrendLabel(getBiasData('bias_trend_10d')) }}
                      </span>
                    </div>
                  </div>
                  
                  <div v-if="getBiasData('bias_price_synergy') !== null || getBiasData('bias_volume_synergy') !== null" class="bias-synergy">
                    <h5>协同指标</h5>
                    <div class="synergy-stats">
                      <div v-if="getBiasData('bias_price_synergy') !== null" class="synergy-item">
                        <span class="synergy-label">Bias-价格协同</span>
                        <span class="synergy-value" :class="getSynergyClass(getBiasData('bias_price_synergy'))">
                          {{ formatSynergy(getBiasData('bias_price_synergy')) }}
                        </span>
                      </div>
                      <div v-if="getBiasData('bias_volume_synergy') !== null" class="synergy-item">
                        <span class="synergy-label">Bias-成交量协同</span>
                        <span class="synergy-value" :class="getSynergyClass(getBiasData('bias_volume_synergy'))">
                          {{ formatSynergy(getBiasData('bias_volume_synergy')) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- 维度分析展示 -->
              <div v-if="report.visualization_data?.dimension_analysis || report.comprehensive_data?.dimension_analysis" class="analysis-section">
                <h4>📊 维度分析</h4>
                <div class="dimension-analysis">
                  <div class="dimension-scores">
                    <div v-if="getDimensionData('price_score') !== null" class="dimension-item">
                      <span class="dimension-label">价格维度得分</span>
                      <div class="dimension-value-container">
                        <el-progress 
                          :percentage="getDimensionData('price_score') * 100" 
                          :color="getDimensionColor(getDimensionData('price_score'))"
                          :stroke-width="12"
                        />
                        <span class="dimension-value">{{ formatDimensionScore(getDimensionData('price_score')) }}</span>
                      </div>
                      <div v-if="getDimensionData('price_trend_persistence') !== null" class="dimension-detail">
                        趋势持续性: {{ formatDimensionScore(getDimensionData('price_trend_persistence')) }}
                      </div>
                      <div v-if="getDimensionData('price_volatility') !== null" class="dimension-detail">
                        波动率: {{ (getDimensionData('price_volatility') * 100).toFixed(2) }}%
                      </div>
                    </div>
                    
                    <div v-if="getDimensionData('frequency_score') !== null" class="dimension-item">
                      <span class="dimension-label">频率维度得分</span>
                      <div class="dimension-value-container">
                        <el-progress 
                          :percentage="getDimensionData('frequency_score') * 100" 
                          :color="getDimensionColor(getDimensionData('frequency_score'))"
                          :stroke-width="12"
                        />
                        <span class="dimension-value">{{ formatDimensionScore(getDimensionData('frequency_score')) }}</span>
                      </div>
                      <div v-if="getDimensionData('rising_concentration') !== null" class="dimension-detail">
                        上涨集中度: {{ formatDimensionScore(getDimensionData('rising_concentration')) }}
                      </div>
                      <div v-if="getDimensionData('false_prosperity_detected') !== null" class="dimension-detail">
                        虚假繁荣检测: {{ getDimensionData('false_prosperity_detected') ? '已检测' : '未检测' }}
                      </div>
                    </div>
                    
                    <div v-if="getDimensionData('volume_score') !== null" class="dimension-item">
                      <span class="dimension-label">成交量维度得分</span>
                      <div class="dimension-value-container">
                        <el-progress 
                          :percentage="getDimensionData('volume_score') * 100" 
                          :color="getDimensionColor(getDimensionData('volume_score'))"
                          :stroke-width="12"
                        />
                        <span class="dimension-value">{{ formatDimensionScore(getDimensionData('volume_score')) }}</span>
                      </div>
                      <div v-if="getDimensionData('volume_consecutive_days') !== null" class="dimension-detail">
                        连续放量天数: {{ getDimensionData('volume_consecutive_days') }}天
                      </div>
                      <div v-if="getDimensionData('volume_price_correlation') !== null" class="dimension-detail">
                        量价相关系数: {{ formatDimensionScore(getDimensionData('volume_price_correlation')) }}
                      </div>
                    </div>
                  </div>
                  
                  <div v-if="getDimensionData('dimension_balance') !== null" class="dimension-balance">
                    <h5>维度均衡性</h5>
                    <div class="balance-indicator">
                      <el-progress 
                        :percentage="getDimensionData('dimension_balance') * 100" 
                        :color="getBalanceColor(getDimensionData('dimension_balance'))"
                        :stroke-width="16"
                      />
                      <span class="balance-label">
                        {{ getBalanceLabel(getDimensionData('dimension_balance')) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- 信号质量分析 -->
              <div v-if="report.visualization_data?.signal_quality_analysis || report.comprehensive_data?.signal_quality_analysis" class="analysis-section">
                <h4>📊 信号质量分析</h4>
                <div class="signal-quality-analysis">
                  <div class="signal-quality-stats">
                    <div v-if="getSignalQualityData('high_quality_count') !== null" class="quality-stat">
                      <span class="quality-label">高质量信号</span>
                      <span class="quality-value positive">{{ getSignalQualityData('high_quality_count') }}</span>
                      <span class="quality-percentage">
                        ({{ formatPercentage(getSignalQualityData('high_quality_count'), getSignalQualityData('total_signals')) }})
                      </span>
                    </div>
                    <div v-if="getSignalQualityData('medium_quality_count') !== null" class="quality-stat">
                      <span class="quality-label">中等质量信号</span>
                      <span class="quality-value warning">{{ getSignalQualityData('medium_quality_count') }}</span>
                      <span class="quality-percentage">
                        ({{ formatPercentage(getSignalQualityData('medium_quality_count'), getSignalQualityData('total_signals')) }})
                      </span>
                    </div>
                    <div v-if="getSignalQualityData('low_quality_count') !== null" class="quality-stat">
                      <span class="quality-label">低质量信号</span>
                      <span class="quality-value negative">{{ getSignalQualityData('low_quality_count') }}</span>
                      <span class="quality-percentage">
                        ({{ formatPercentage(getSignalQualityData('low_quality_count'), getSignalQualityData('total_signals')) }})
                      </span>
                    </div>
                  </div>
                  
                  <div v-if="getSignalQualityData('filter_reasons')" class="filter-reasons">
                    <h5>信号过滤原因统计</h5>
                    <div class="reasons-list">
                      <div 
                        v-for="(count, reason) in getSignalQualityData('filter_reasons')" 
                        :key="reason"
                        class="reason-item"
                      >
                        <span class="reason-label">{{ reason }}</span>
                        <span class="reason-count">{{ count }}次</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-else-if="report.comprehensive_data" class="visualization-analysis">
              <div class="analysis-section">
                <h4>📊 性能指标分析</h4>
                <div class="metrics-grid">
                  <div class="metric-item">
                    <span class="metric-label">总收益率</span>
                    <span class="metric-value" :class="report.comprehensive_data.performance_metrics.total_return >= 0 ? 'positive' : 'negative'">
                      {{ (report.comprehensive_data.performance_metrics.total_return * 100).toFixed(2) }}%
                    </span>
                  </div>
                  <div class="metric-item">
                    <span class="metric-label">年化收益率</span>
                    <span class="metric-value" :class="report.comprehensive_data.performance_metrics.annual_return >= 0 ? 'positive' : 'negative'">
                      {{ (report.comprehensive_data.performance_metrics.annual_return * 100).toFixed(2) }}%
                    </span>
                  </div>
                  <div class="metric-item">
                    <span class="metric-label">最大回撤</span>
                    <span class="metric-value negative">
                      {{ (report.comprehensive_data.performance_metrics.max_drawdown * 100).toFixed(2) }}%
                    </span>
                  </div>
                  <div class="metric-item">
                    <span class="metric-label">夏普比率</span>
                    <span class="metric-value">
                      {{ report.comprehensive_data.performance_metrics.sharpe_ratio.toFixed(2) }}
                    </span>
                  </div>
                  <div class="metric-item">
                    <span class="metric-label">波动率</span>
                    <span class="metric-value">
                      {{ (report.comprehensive_data.performance_metrics.volatility * 100).toFixed(2) }}%
                    </span>
                  </div>
                  <div class="metric-item">
                    <span class="metric-label">胜率</span>
                    <span class="metric-value">
                      {{ (report.comprehensive_data.performance_metrics.win_rate * 100).toFixed(2) }}%
                    </span>
                  </div>
                </div>
              </div>
              
              <div class="analysis-section">
                <h4>💰 交易分析</h4>
                <div class="trade-analysis">
                  <div class="trade-summary">
                    <div class="trade-stat">
                      <span class="stat-label">总交易次数</span>
                      <span class="stat-value">{{ report.comprehensive_data.trade_analysis.total_trades }}</span>
                    </div>
                    <div class="trade-stat">
                      <span class="stat-label">盈利交易</span>
                      <span class="stat-value positive">{{ report.comprehensive_data.trade_analysis.winning_trades }}</span>
                    </div>
                    <div class="trade-stat">
                      <span class="stat-label">亏损交易</span>
                      <span class="stat-value negative">{{ report.comprehensive_data.trade_analysis.losing_trades }}</span>
                    </div>
                    <div class="trade-stat">
                      <span class="stat-label">盈利因子</span>
                      <span class="stat-value">{{ report.comprehensive_data.trade_analysis.profit_factor.toFixed(2) }}</span>
                    </div>
                  </div>
                  
                  <div class="trade-distribution">
                    <h5>盈亏分布</h5>
                    <div class="distribution-stats">
                      <div class="dist-item">
                        <span class="dist-label">平均盈利</span>
                        <span class="dist-value positive">
                          ¥{{ report.comprehensive_data.trade_analysis.avg_win.toFixed(2) }}
                        </span>
                      </div>
                      <div class="dist-item">
                        <span class="dist-label">平均亏损</span>
                        <span class="dist-value negative">
                          ¥{{ report.comprehensive_data.trade_analysis.avg_loss.toFixed(2) }}
                        </span>
                      </div>
                      <div class="dist-item">
                        <span class="dist-label">平均持仓天数</span>
                        <span class="dist-value">
                          {{ report.comprehensive_data.trade_analysis.avg_holding_days.toFixed(1) }}天
                        </span>
                      </div>
                      <div class="dist-item">
                        <span class="dist-label">最佳交易</span>
                        <span class="dist-value positive">
                          ¥{{ report.comprehensive_data.trade_analysis.best_trade.toFixed(2) }}
                        </span>
                      </div>
                      <div class="dist-item">
                        <span class="dist-label">最差交易</span>
                        <span class="dist-value negative">
                          ¥{{ report.comprehensive_data.trade_analysis.worst_trade.toFixed(2) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              <div class="analysis-section">
                <h4>📈 风险分析</h4>
                <div class="risk-analysis">
                  <div class="risk-metrics">
                    <div class="risk-item">
                      <span class="risk-label">最大连续亏损</span>
                      <span class="risk-value negative">
                        {{ report.comprehensive_data.risk_metrics.consecutive_losses }}次
                      </span>
                    </div>
                    <div class="risk-item">
                      <span class="risk-label">VaR (95%)</span>
                      <span class="risk-value">
                        ¥{{ report.comprehensive_data.risk_metrics.var_95.toFixed(2) }}
                      </span>
                    </div>
                    <div class="risk-item">
                      <span class="risk-label">VaR (99%)</span>
                      <span class="risk-value">
                        ¥{{ report.comprehensive_data.risk_metrics.var_99.toFixed(2) }}
                      </span>
                    </div>
                    <div class="risk-item">
                      <span class="risk-label">最大亏损</span>
                      <span class="risk-value negative">
                        ¥{{ report.comprehensive_data.risk_metrics.maximum_loss.toFixed(2) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="report-details-empty">
            <el-empty description="暂无详细分析数据" :image-size="100" />
          </div>
          
          <!-- 如果有图表数据 -->
          <div class="report-charts" v-if="report.charts && report.charts.length > 0">
            <h3>数据图表</h3>
            <div class="charts-grid">
              <div 
                v-for="(chart, index) in report.charts" 
                :key="index"
                class="chart-item"
              >
                <el-card>
                  <h4>{{ chart.title }}</h4>
                  <div class="chart-container">
                    <!-- 这里可以根据图表类型渲染不同的图表组件 -->
                    <div class="chart-placeholder">
                      图表: {{ chart.type }}
                    </div>
                  </div>
                </el-card>
              </div>
            </div>
          </div>
          
          <!-- 如果有推荐股票 -->
          <div class="report-stocks" v-if="reportStocks && reportStocks.length > 0">
            <h3>推荐股票</h3>
            <el-table :data="reportStocks" style="width: 100%">
              <el-table-column prop="symbol" label="股票代码" width="120" />
              <el-table-column prop="name" label="股票名称" width="150" />
              <el-table-column prop="price" label="当前价格" width="120">
                <template #default="scope">
                  ¥{{ scope.row.price?.toFixed(2) }}
                </template>
              </el-table-column>
              <el-table-column prop="signal_strength" label="信号强度" width="120">
                <template #default="scope">
                  <el-tag 
                    :type="getSignalType(scope.row.signal_strength)"
                    size="small"
                  >
                    {{ (scope.row.signal_strength * 100).toFixed(1) }}%
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="reason" label="推荐理由" />
            </el-table>
          </div>

          <!-- 如果有交易记录 -->
          <div class="report-trades" v-if="reportTrades && reportTrades.length > 0">
            <h3>详细交易记录</h3>
            <el-table :data="reportTrades" style="width: 100%" stripe border>
              <el-table-column prop="stock_code" label="股票代码" width="100" sortable />
              <el-table-column prop="entry_date" label="买入日期" width="110" sortable />
              <el-table-column prop="entry_price" label="买入价格" width="100">
                <template #default="scope">
                  ¥{{ Number(scope.row.entry_price).toFixed(2) }}
                </template>
              </el-table-column>
              <el-table-column prop="exit_time" label="卖出日期" width="110">
                <template #default="scope">
                  {{ scope.row.exit_time ? formatDateOnly(scope.row.exit_time) : '持仓中' }}
                </template>
              </el-table-column>
              <el-table-column prop="exit_price" label="卖出价格" width="100">
                <template #default="scope">
                  {{ scope.row.exit_price ? '¥' + Number(scope.row.exit_price).toFixed(2) : '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="quantity" label="数量" width="80" />
              <el-table-column prop="pnl" label="盈亏" width="110">
                <template #default="scope">
                  <span :class="scope.row.pnl >= 0 ? 'text-green-600' : 'text-red-600'">
                    ¥{{ Number(scope.row.pnl).toFixed(2) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="pnl_percent" label="盈亏比" width="100">
                <template #default="scope">
                  <span :class="scope.row.pnl_percent >= 0 ? 'text-green-600' : 'text-red-600'">
                    {{ formatPnlPercent(scope.row) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="holding_period" label="持有(天)" width="90" />
              <el-table-column prop="exit_reason" label="退出原因" min-width="120" />
            </el-table>
          </div>
        </el-card>
      </div>
    </div>
    
    <!-- 如果没有报告数据且没有错误，显示提示 -->
    <div v-else class="error-container">
      <el-result
        icon="warning"
        title="暂无数据"
        sub-title="报告数据为空，请检查报告ID是否正确或报告是否已生成"
      >
        <template #extra>
          <el-button type="primary" @click="loadReport">重新加载</el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { API_BASE } from '@/config/api'

const route = useRoute()
const router = useRouter()

// 定义 props
const props = defineProps({
  report: {
    type: Object,
    default: null
  }
})

// 注入服务
const pvfrsApi = inject('pvfrsApi')

// 获取认证头部的辅助函数
const getAuthHeaders = () => {
  const token = localStorage.getItem('admin_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const loading = ref(true)
const error = ref('')
const report = ref(null)

// 确保 stocks 始终是数组
const reportStocks = computed(() => {
  if (!report.value || !report.value.stocks) return []
  return Array.isArray(report.value.stocks) ? report.value.stocks : []
})

// 确保 trades 始终是数组
const reportTrades = computed(() => {
  if (!report.value || !report.value.trades) return []
  return Array.isArray(report.value.trades) ? report.value.trades : []
})

// 加载报告详情
const loadReport = async () => {
  try {
    loading.value = true
    error.value = ''
    
    // 优先使用 prop 中的 report，如果没有则从路由参数获取
    let reportId = null
    let taskId = null
    
    if (props.report) {
      // 如果通过 prop 传递了报告数据，优先使用
      reportId = props.report.id || props.report.report_id
      taskId = props.report.taskId || props.report.task_id
      console.log('使用 prop 中的报告数据，reportId:', reportId, 'taskId:', taskId)
      
      // 如果 prop 中已经有完整的报告数据，可以直接使用
      if (props.report._rawData || props.report.totalReturn !== undefined) {
        console.log('prop 中包含完整报告数据，直接使用')
        report.value = props.report
        loading.value = false
        return
      }
    }
    
    // 如果没有 prop，尝试从路由参数获取
    if (!reportId) {
      reportId = route.params.id
      console.log('从路由参数获取 reportId:', reportId)
    }
    
    // 如果仍然没有 reportId，报错
    if (!reportId) {
      error.value = '无法获取报告ID，请提供有效的报告ID'
      loading.value = false
      return
    }
    
    // 尝试通过报告ID获取报告详情
    let reportData = null
    let lastError = null
    
    // 方法1: 尝试通过任务ID获取报告（如果有 taskId）
    if (taskId) {
      try {
        console.log('尝试方法1: 通过任务ID获取报告，taskId:', taskId)
        const response = await fetch(`${API_BASE}/api/admin/pvfrs/backtest/report/${taskId}`, {
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
          }
        })
        
        console.log('方法1响应状态:', response.status, response.statusText)
        
        if (response.ok) {
          const data = await response.json()
          console.log('方法1返回数据:', data)
          // 格式化器可能返回不同的结构
          if (data.data) {
            reportData = data.data
          } else if (data.report_id || data.total_return !== undefined) {
            reportData = data
          } else {
            // 可能是格式化后的数据，直接使用
            reportData = data
          }
        } else {
          const errorText = await response.text()
          console.warn('方法1失败:', response.status, errorText)
          lastError = `HTTP ${response.status}: ${errorText}`
        }
      } catch (e) {
        console.warn('方法1异常:', e)
        lastError = e.message
      }
    } else if (reportId) {
      // 如果没有 taskId，尝试使用 reportId 作为 taskId（仅在 reportId 有效时）
      try {
        console.log('尝试方法1: 通过 reportId 作为 taskId 获取报告，reportId:', reportId)
        const response = await fetch(`${API_BASE}/api/admin/pvfrs/backtest/report/${reportId}`, {
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
          }
        })
        
        console.log('方法1响应状态:', response.status, response.statusText)
        
        if (response.ok) {
          const data = await response.json()
          console.log('方法1返回数据:', data)
          // 格式化器可能返回不同的结构
          if (data.data) {
            reportData = data.data
          } else if (data.report_id || data.total_return !== undefined) {
            reportData = data
          } else {
            // 可能是格式化后的数据，直接使用
            reportData = data
          }
        } else {
          const errorText = await response.text()
          console.warn('方法1失败:', response.status, errorText)
          lastError = `HTTP ${response.status}: ${errorText}`
        }
      } catch (e) {
        console.warn('方法1异常:', e)
        lastError = e.message
      }
    }
    
    // 方法2: 如果方法1失败，尝试直接获取报告详情（仅在 reportId 有效时）
    if (!reportData && reportId) {
      try {
        console.log('尝试方法2: 直接获取报告详情，reportId:', reportId)
        const response = await fetch(`${API_BASE}/api/admin/pvfrs/reports/${reportId}`, {
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
          }
        })
        
        console.log('方法2响应状态:', response.status, response.statusText)
        
        if (response.ok) {
          const data = await response.json()
          console.log('方法2返回数据:', data)
          if (data.success && data.data) {
            reportData = data.data
          } else if (data.report_id || data.total_return !== undefined) {
            reportData = data
          }
        } else {
          const errorText = await response.text()
          console.warn('方法2失败:', response.status, errorText)
          lastError = `HTTP ${response.status}: ${errorText}`
        }
      } catch (e) {
        console.warn('方法2异常:', e)
        lastError = e.message
      }
    }
    
    // 方法3: 尝试使用 pvfrsApi.getReport（仅在 reportId 有效时）
    if (!reportData && reportId && pvfrsApi && pvfrsApi.getReport) {
      try {
        console.log('尝试方法3: 使用 pvfrsApi.getReport，reportId:', reportId)
        const response = await pvfrsApi.getReport(reportId)
        console.log('方法3返回数据:', response)
        reportData = response.data || response
      } catch (e) {
        console.warn('方法3异常:', e)
        lastError = e.message
      }
    }
    
    if (reportData) {
      console.log('成功获取报告数据，开始转换:', reportData)
      console.log('报告数据完整结构:', JSON.stringify(reportData, null, 2))
      
      // 检查数据是否在嵌套结构中
      let actualData = reportData
      if (reportData.data) {
        actualData = reportData.data
        console.log('数据在 data 字段中:', actualData)
      }
      
      // 提取 comprehensive_data（如果存在）
      const comprehensiveData = actualData.comprehensive_data || actualData.comprehensiveData
      if (comprehensiveData) {
        console.log('找到 comprehensive_data:', comprehensiveData)
        // 合并 comprehensive_data 中的数据到 actualData
        actualData = {
          ...actualData,
          ...comprehensiveData,
          // 保留原始字段
          report_id: actualData.report_id || actualData.id,
          task_id: actualData.task_id,
          config: actualData.config,
          created_at: actualData.created_at || comprehensiveData.report_metadata?.generated_at
        }
      }
      
      // 转换报告数据格式以匹配前端组件期望的格式
      report.value = {
        id: actualData.report_id || actualData.id || reportId,
        title: actualData.title || `PVFARS策略回测报告 - ${actualData.report_id || reportId}`,
        type: actualData.type || actualData.report_type || '回测报告',
        created_at: actualData.created_at || actualData.createdAt || new Date().toISOString(),
        summary: actualData.summary || generateSummaryFromReport(actualData),
        details: actualData.details || generateDetailsFromReport(actualData),
        charts: actualData.charts || actualData.visualization_data || [],
        stocks: actualData.stocks || actualData.stock_list || [],
        trades: actualData.trades || [],
        // 保留原始数据以便调试
        _rawData: actualData
      }
      
      console.log('报告数据转换完成:', report.value)
      console.log('摘要内容:', report.value.summary)
      console.log('详细信息内容:', report.value.details)
      console.log('是否有图表:', report.value.charts?.length || 0)
      console.log('是否有股票:', report.value.stocks?.length || 0)
    } else {
      const errorMsg = lastError || '无法获取报告数据，所有方法都失败了'
      console.error('获取报告数据失败:', errorMsg)
      error.value = `加载报告详情失败: ${errorMsg}`
    }
    
  } catch (err) {
    console.error('加载报告详情异常:', err)
    error.value = `加载报告详情失败: ${err.message || '请稍后重试'}`
  } finally {
    loading.value = false
    console.log('加载完成，loading:', loading.value, 'error:', error.value, 'report:', report.value ? '有数据' : '无数据')
  }
}

// 从报告数据生成摘要
const generateSummaryFromReport = (reportData) => {
  const metrics = []
  
  // 尝试多种可能的字段名
  const totalReturn = reportData.total_return ?? reportData.totalReturn ?? reportData.performance_metrics?.total_return
  const annualReturn = reportData.annual_return ?? reportData.annualReturn ?? reportData.performance_metrics?.annual_return
  const maxDrawdown = reportData.max_drawdown ?? reportData.maxDrawdown ?? reportData.risk_metrics?.max_drawdown
  const sharpeRatio = reportData.sharpe_ratio ?? reportData.sharpeRatio ?? reportData.performance_metrics?.sharpe_ratio
  const winRate = reportData.win_rate ?? reportData.winRate ?? reportData.trade_analysis?.win_rate
  
  if (totalReturn !== undefined && totalReturn !== null) {
    const color = totalReturn >= 0 ? '#10b981' : '#ef4444'
    metrics.push(`<span style="color: ${color}; font-weight: 600;">总收益率: ${(totalReturn * 100).toFixed(2)}%</span>`)
  }
  if (annualReturn !== undefined && annualReturn !== null) {
    const color = annualReturn >= 0 ? '#10b981' : '#ef4444'
    metrics.push(`<span style="color: ${color}; font-weight: 600;">年化收益率: ${(annualReturn * 100).toFixed(2)}%</span>`)
  }
  if (maxDrawdown !== undefined && maxDrawdown !== null) {
    metrics.push(`<span style="color: #ef4444; font-weight: 600;">最大回撤: ${(maxDrawdown * 100).toFixed(2)}%</span>`)
  }
  if (sharpeRatio !== undefined && sharpeRatio !== null) {
    metrics.push(`夏普比率: ${sharpeRatio.toFixed(2)}`)
  }
  if (winRate !== undefined && winRate !== null) {
    metrics.push(`胜率: ${(winRate * 100).toFixed(2)}%`)
  }
  
  // 获取回测期间
  let periodInfo = ''
  if (reportData.config) {
    periodInfo = `<p><strong>回测期间:</strong> ${reportData.config.start_date || ''} 至 ${reportData.config.end_date || ''}</p>`
  } else if (reportData.report_metadata?.period) {
    const period = reportData.report_metadata.period
    periodInfo = `<p><strong>回测期间:</strong> ${period.start_date || ''} 至 ${period.end_date || ''}</p>`
  }
  
  return `<div class="report-summary-content">
    <p>本报告基于PVFARS策略回测分析。</p>
    ${metrics.length > 0 ? `<div class="metrics-grid"><p><strong>核心指标:</strong></p><p>${metrics.join(' | ')}</p></div>` : ''}
    ${periodInfo}
  </div>`
}

// 从报告数据生成详细信息
const generateDetailsFromReport = (reportData) => {
  let details = '<div class="report-details-content">'
  
  // 交易分析
  const trades = reportData.trades || reportData.trade_analysis?.trades || []
  if (trades && Array.isArray(trades) && trades.length > 0) {
    details += `<div class="detail-section"><h4>交易记录</h4>`
    details += `<p>总交易次数: <strong>${trades.length}</strong></p>`
    
    const winningTrades = trades.filter(t => (t.pnl ?? t.profit) > 0).length
    const losingTrades = trades.filter(t => (t.pnl ?? t.profit) < 0).length
    details += `<p>盈利交易: <strong style="color: #10b981;">${winningTrades}</strong> | 亏损交易: <strong style="color: #ef4444;">${losingTrades}</strong></p>`
    
    if (reportData.trade_analysis) {
      const ta = reportData.trade_analysis
      if (ta.avg_profit !== undefined) details += `<p>平均盈利: ${(ta.avg_profit).toFixed(2)} 元</p>`
      if (ta.avg_loss !== undefined) details += `<p>平均亏损: ${(ta.avg_loss).toFixed(2)} 元</p>`
    }
    details += `</div>`
  } else if (reportData.trade_analysis) {
    const ta = reportData.trade_analysis
    details += `<div class="detail-section"><h4>交易分析</h4>`
    if (ta.total_trades !== undefined) details += `<p>总交易次数: <strong>${ta.total_trades}</strong></p>`
    if (ta.winning_trades !== undefined) details += `<p>盈利交易: <strong style="color: #10b981;">${ta.winning_trades}</strong></p>`
    if (ta.losing_trades !== undefined) details += `<p>亏损交易: <strong style="color: #ef4444;">${ta.losing_trades}</strong></p>`
    if (ta.avg_profit !== undefined) details += `<p>平均盈利: ${(ta.avg_profit).toFixed(2)} 元</p>`
    if (ta.avg_loss !== undefined) details += `<p>平均亏损: ${(ta.avg_loss).toFixed(2)} 元</p>`
    details += `</div>`
  }
  
  // 配置信息
  if (reportData.config || reportData.report_metadata) {
    details += `<div class="detail-section"><h4>配置信息</h4>`
    const config = reportData.config || {}
    const metadata = reportData.report_metadata || {}
    
    const initialCapital = config.initial_capital ?? metadata.initial_capital
    if (initialCapital) {
      details += `<p>初始资金: <strong>${Number(initialCapital).toLocaleString('zh-CN')} 元</strong></p>`
    }
    
    const stockPool = config.stock_pool || []
    if (stockPool && stockPool.length > 0) {
      details += `<p>股票池: <strong>${stockPool.length} 只股票</strong> (${stockPool.slice(0, 5).join(', ')}${stockPool.length > 5 ? '...' : ''})</p>`
    }
    
    if (metadata.final_capital) {
      details += `<p>最终资金: <strong>${Number(metadata.final_capital).toLocaleString('zh-CN')} 元</strong></p>`
    }
    details += `</div>`
  }
  
  // 风险指标
  if (reportData.risk_metrics) {
    const rm = reportData.risk_metrics
    details += `<div class="detail-section"><h4>风险指标</h4>`
    if (rm.max_drawdown !== undefined) details += `<p>最大回撤: <strong style="color: #ef4444;">${(rm.max_drawdown * 100).toFixed(2)}%</strong></p>`
    if (rm.volatility !== undefined) details += `<p>波动率: ${(rm.volatility * 100).toFixed(2)}%</p>`
    if (rm.calmar_ratio !== undefined) details += `<p>卡玛比率: ${rm.calmar_ratio.toFixed(2)}</p>`
    details += `</div>`
  }
  
  details += '</div>'
  return details || '<div class="report-details-content"><p>暂无详细分析数据</p></div>'
}

// 返回上一页
const goBack = () => {
  router.go(-1)
}

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取Bias数据
const getBiasData = (key) => {
  if (!report.value) return null
  const biasAnalysis = report.value.visualization_data?.bias_analysis || 
                       report.value.comprehensive_data?.bias_analysis ||
                       report.value.bias_analysis
  return biasAnalysis?.[key] ?? null
}

// 格式化Bias得分
const formatBiasScore = (score) => {
  if (score === null || score === undefined) return '-'
  return (score * 100).toFixed(1)
}

// 获取Bias得分样式类
const getBiasScoreClass = (score) => {
  if (score === null || score === undefined) return ''
  if (score >= 0.8) return 'positive'
  if (score >= 0.6) return 'warning'
  return 'negative'
}

// 获取Bias值样式类
const getBiasValueClass = (value) => {
  if (value === null || value === undefined) return ''
  const absValue = Math.abs(value)
  if (absValue > 0.10) return 'warning' // 超过10%需要关注
  if (value > 0) return 'positive'
  return 'negative'
}

// 获取Bias趋势样式类
const getBiasTrendClass = (trend) => {
  if (trend === null || trend === undefined) return ''
  if (trend > 0) return 'positive'
  if (trend < 0) return 'negative'
  return ''
}

// 获取Bias趋势标签
const getBiasTrendLabel = (trend) => {
  if (trend === null || trend === undefined) return '-'
  if (trend > 0.02) return '上升'
  if (trend < -0.02) return '下降'
  return '平稳'
}

// 格式化协同指标
const formatSynergy = (synergy) => {
  if (synergy === null || synergy === undefined) return '-'
  return (synergy * 100).toFixed(1) + '%'
}

// 获取维度数据
const getDimensionData = (key) => {
  if (!report.value) return null
  const dimensionAnalysis = report.value.visualization_data?.dimension_analysis || 
                            report.value.comprehensive_data?.dimension_analysis ||
                            report.value.dimension_analysis
  return dimensionAnalysis?.[key] ?? null
}

// 格式化维度得分
const formatDimensionScore = (score) => {
  if (score === null || score === undefined) return '-'
  return (score * 100).toFixed(1)
}

// 获取维度颜色
const getDimensionColor = (score) => {
  if (score === null || score === undefined) return '#909399'
  if (score >= 0.8) return '#67c23a'
  if (score >= 0.6) return '#e6a23c'
  return '#f56c6c'
}

// 获取均衡性颜色
const getBalanceColor = (balance) => {
  if (balance === null || balance === undefined) return '#909399'
  if (balance >= 0.8) return '#67c23a'
  if (balance >= 0.6) return '#e6a23c'
  return '#f56c6c'
}

// 获取均衡性标签
const getBalanceLabel = (balance) => {
  if (balance === null || balance === undefined) return '-'
  if (balance >= 0.8) return '均衡'
  if (balance >= 0.6) return '较均衡'
  return '不均衡'
}

// 获取信号质量数据
const getSignalQualityData = (key) => {
  if (!report.value) return null
  const signalQualityAnalysis = report.value.visualization_data?.signal_quality_analysis || 
                                report.value.comprehensive_data?.signal_quality_analysis ||
                                report.value.signal_quality_analysis
  return signalQualityAnalysis?.[key] ?? null
}

// 格式化百分比
const formatPercentage = (count, total) => {
  if (!total || total === 0) return '0%'
  return ((count / total) * 100).toFixed(1) + '%'
}

// 格式化日期（仅日期部分）
const formatDateOnly = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

// 获取信号强度类型
const getSignalType = (strength) => {
  if (strength >= 0.8) return 'success'
  if (strength >= 0.6) return 'warning'
  return 'info'
}

// 盈亏比显示：优先用后端提供的 pnl_percent（小数比例），若历史数据为0则尝试用买卖价兜底计算
const formatPnlPercent = (row) => {
  if (!row) return '-'
  const raw = row.pnl_percent
  const pnl = Number(row.pnl)
  const entry = Number(row.entry_price)
  const exit = Number(row.exit_price)

  let ratio = Number(raw)
  if (Number.isNaN(ratio)) ratio = 0

  // 若 pnl 非0但 ratio=0，且有买卖价，则用价格计算兜底（兼容历史数据入库缺字段）
  if ((raw === null || raw === undefined || ratio === 0) && pnl !== 0 && entry > 0 && exit > 0) {
    ratio = (exit - entry) / entry
  }

  if (Number.isNaN(ratio)) return '-'
  return `${(ratio * 100).toFixed(2)}%`
}

// 监听 prop 变化
watch(() => props.report, (newReport) => {
  if (newReport) {
    console.log('report prop 变化，重新加载报告')
    loadReport()
  }
}, { immediate: false })

onMounted(() => {
  // 如果已经有 prop 中的报告数据，直接使用
  if (props.report && (props.report._rawData || props.report.totalReturn !== undefined)) {
    console.log('onMounted: 使用 prop 中的报告数据')
    report.value = props.report
    loading.value = false
  } else {
    // 否则加载报告
    loadReport()
  }
})
</script>

<style scoped>
.report-detail {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.loading-container,
.error-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.report-header {
  margin-bottom: 20px;
}

.header-content h1 {
  margin: 0 0 10px 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.date {
  color: #6b7280;
  font-size: 14px;
}

.report-card {
  margin-bottom: 20px;
}

.report-summary {
  margin-bottom: 24px;
  line-height: 1.6;
}

.report-summary-content {
  padding: 16px 0;
}

.metrics-grid {
  margin: 16px 0;
  padding: 12px;
  background-color: #f9fafb;
  border-radius: 6px;
  border-left: 3px solid #3b82f6;
}

.metrics-grid p {
  margin: 8px 0;
  line-height: 1.8;
}

.report-details-content {
  padding: 16px 0;
}

.detail-section {
  margin-bottom: 24px;
  padding: 16px;
  background-color: #ffffff;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}

.detail-section h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  padding-bottom: 8px;
  border-bottom: 2px solid #3b82f6;
}

.detail-section p {
  margin: 8px 0;
  line-height: 1.6;
  color: #374151;
}

.report-details,
.report-charts,
.report-stocks {
  margin-top: 32px;
}

.report-details h3,
.report-charts h3,
.report-stocks h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e5e7eb;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
  margin-top: 16px;
}

.chart-item h4 {
  font-size: 16px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 12px;
}

.chart-container {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f9fafb;
  border-radius: 8px;
  border: 1px dashed #d1d5db;
}

.chart-placeholder {
  color: #6b7280;
  font-size: 14px;
}

.summary-object,
.details-object {
  background-color: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  padding: 16px;
  margin: 12px 0;
}

.summary-object h4,
.details-object h4 {
  margin: 0 0 12px 0;
  color: #495057;
  font-size: 16px;
  font-weight: 600;
}

.summary-object pre,
.details-object pre {
  background-color: #f1f3f4;
  border: 1px solid #e1e5e9;
  border-radius: 4px;
  padding: 12px;
  font-size: 12px;
  color: #374151;
  overflow-x: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.summary-content {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.summary-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.summary-item.full-width {
  grid-column: 1 / -1;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.summary-item:hover {
  background-color: #f9fafb;
  border-color: #d1d5db;
}

.summary-item .label {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

.summary-item .positive {
  color: #10b981;
  font-weight: 600;
}

.summary-item .negative {
  color: #ef4444;
  font-weight: 600;
  font-style: italic;
  padding: 20px;
}

.highlights {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.highlight-tag {
  background-color: #10b981;
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.warnings {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.warning-tag {
  background-color: #f59e0b;
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.recommendation {
  background-color: #3b82f6;
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  width: 100%;
}

.summary-text {
  background-color: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 4px;
  padding: 12px;
  font-size: 14px;
  line-height: 1.6;
  color: #374151;
  width: 100%;
}

.summary-empty,
.details-empty {
  text-align: center;
  color: #6c757d;
  font-style: italic;
  padding: 20px;
}

.visualization-analysis {
  margin-top: 16px;
}

.comprehensive-analysis {
  margin-top: 16px;
}

.analysis-section {
  margin-bottom: 32px;
  padding: 20px;
  background-color: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.analysis-section h4 {
  margin: 0 0 16px 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  padding-bottom: 8px;
  border-bottom: 2px solid #3b82f6;
}

.analysis-section h5 {
  margin: 16px 0 12px 0;
  font-size: 16px;
  font-weight: 500;
  color: #374151;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.metric-item:hover {
  background-color: #f1f3f4;
  border-color: #d1d5db;
}

.metric-label {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

.metric-value {
  font-weight: 600;
  font-size: 15px;
}

/* 乖离率分析样式 */
.bias-analysis {
  margin-top: 16px;
}

.bias-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.bias-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.bias-item:hover {
  background-color: #f1f3f4;
  border-color: #d1d5db;
}

.bias-label {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

.bias-value {
  font-size: 16px;
  font-weight: 600;
}

.bias-synergy {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e5e7eb;
}

.synergy-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.synergy-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 6px;
}

.synergy-label {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

.synergy-value {
  font-size: 16px;
  font-weight: 600;
}

/* 维度分析样式 */
.dimension-analysis {
  margin-top: 16px;
}

.dimension-scores {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.dimension-item {
  padding: 16px;
  background-color: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 8px;
}

.dimension-label {
  font-weight: 600;
  color: #374151;
  font-size: 15px;
  margin-bottom: 12px;
  display: block;
}

.dimension-value-container {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.dimension-value {
  font-size: 18px;
  font-weight: 600;
  min-width: 60px;
}

.dimension-detail {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}

.dimension-balance {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e5e7eb;
}

.balance-indicator {
  display: flex;
  align-items: center;
  gap: 16px;
}

.balance-label {
  font-weight: 600;
  font-size: 16px;
  min-width: 80px;
}

/* 信号质量分析样式 */
.signal-quality-analysis {
  margin-top: 16px;
}

.signal-quality-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.quality-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  background-color: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 8px;
}

.quality-label {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
  margin-bottom: 8px;
}

.quality-value {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 4px;
}

.quality-percentage {
  font-size: 12px;
  color: #6b7280;
}

.filter-reasons {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e5e7eb;
}

.reasons-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.reason-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background-color: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 6px;
}

.reason-label {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

.reason-count {
  font-weight: 600;
  color: #3b82f6;
  font-size: 14px;
}

.trade-analysis {
  display: grid;
  gap: 20px;
}

.trade-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.trade-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 6px;
}

.stat-label {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

.stat-value {
  font-weight: 600;
  font-size: 15px;
}

.trade-distribution {
  padding: 16px;
  background-color: #fafbfc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.distribution-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.dist-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background-color: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
}

.dist-label {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

.dist-value {
  font-weight: 600;
  font-size: 14px;
}

.risk-analysis {
  padding: 16px;
}

.risk-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.risk-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
}

.risk-label {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

.risk-value {
  font-weight: 600;
  font-size: 15px;
}

@media (max-width: 768px) {
  .report-detail {
    padding: 16px;
  }
  
  .charts-grid {
    grid-template-columns: 1fr;
  }
  
  .report-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
</style>