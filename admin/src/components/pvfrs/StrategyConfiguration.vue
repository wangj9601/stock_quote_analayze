<template>
  <div class="strategy-configuration">
    <!-- 配置概览 -->
    <el-row :gutter="20" class="config-overview">
      <el-col :span="8">
        <el-card class="overview-card">
          <div class="card-header">
            <el-icon class="card-icon"><Setting /></el-icon>
            <span class="card-title">当前配置</span>
          </div>
          <div class="card-content">
            <div class="config-item">
              <span class="config-label">配置版本:</span>
              <span class="config-value">{{ currentConfig.version || 'v1.0.0' }}</span>
            </div>
            <div class="config-item">
              <span class="config-label">最后更新:</span>
              <span class="config-value">{{ formatDateTime(currentConfig.updatedAt) }}</span>
            </div>
            <div class="config-item">
              <span class="config-label">配置状态:</span>
              <el-tag :type="currentConfig.isActive ? 'success' : 'warning'">
                {{ currentConfig.isActive ? '已激活' : '未激活' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="overview-card">
          <div class="card-header">
            <el-icon class="card-icon"><DataAnalysis /></el-icon>
            <span class="card-title">策略参数</span>
          </div>
          <div class="card-content">
            <div class="config-item">
              <span class="config-label">买入信号强度:</span>
              <span class="config-value">{{ currentConfig.buySignalStrength || 0.7 }}</span>
            </div>
            <div class="config-item">
              <span class="config-label">卖出信号强度:</span>
              <span class="config-value">{{ currentConfig.sellSignalStrength || 0.8 }}</span>
            </div>
            <div class="config-item">
              <span class="config-label">风险控制等级:</span>
              <el-tag :type="getRiskLevelType(currentConfig.riskLevel)">
                {{ getRiskLevelLabel(currentConfig.riskLevel) }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="overview-card">
          <div class="card-header">
            <el-icon class="card-icon"><TrendCharts /></el-icon>
            <span class="card-title">性能指标</span>
          </div>
          <div class="card-content">
            <div class="config-item">
              <span class="config-label">历史胜率:</span>
              <span class="config-value text-green-600">{{ currentConfig.winRate || 65 }}%</span>
            </div>
            <div class="config-item">
              <span class="config-label">平均收益:</span>
              <span class="config-value text-blue-600">{{ currentConfig.avgReturn || 12.5 }}%</span>
            </div>
            <div class="config-item">
              <span class="config-label">最大回撤:</span>
              <span class="config-value text-red-600">{{ currentConfig.maxDrawdown || 8.2 }}%</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 配置表单 -->
    <el-card class="config-form-card" header="策略参数配置">
      <el-form 
        ref="configFormRef" 
        :model="configForm" 
        :rules="configRules" 
        label-width="180px"
        class="config-form"
      >
        <!-- 买入条件配置 -->
        <el-divider content-position="left">
          <el-icon><TrendCharts /></el-icon>
          买入条件配置
        </el-divider>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="宏观位移最小值" prop="buyMacroDisplacementMin">
              <el-input-number 
                v-model="configForm.buyMacroDisplacementMin" 
                :step="0.001" 
                :precision="4"
                placeholder="Δ > 0"
                class="w-full"
              />
              <div class="form-help">价格相对于起始位置的位移，通常 > 0</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="即时偏离度最小值" prop="buyInstantDeviationMin">
              <el-input-number 
                v-model="configForm.buyInstantDeviationMin" 
                :step="0.001" 
                :precision="4"
                placeholder="d20 > d"
                class="w-full"
              />
              <div class="form-help">当前价格相对于20日均线的偏离度</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="上涨频率优势" prop="buyRisingDaysAdvantage">
              <el-switch v-model="configForm.buyRisingDaysAdvantage" />
              <div class="form-help">要求上涨天数 > 下跌天数（Z > F）</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="效率最小值" prop="buyEfficiencyMin">
              <el-input-number 
                v-model="configForm.buyEfficiencyMin" 
                :step="0.001" 
                :precision="4"
                placeholder="m20 > m"
                class="w-full"
              />
              <div class="form-help">成交量效率指标，m20 > m</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="乖离率最小值" prop="buyBiasMin">
              <el-input-number 
                v-model="configForm.buyBiasMin" 
                :step="0.01" 
                :precision="3"
                placeholder="2%"
                class="w-full"
              />
              <div class="form-help">价格相对于均线的乖离率，通常 > 2%</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="相对位移最小值" prop="buyRelativeDisplacementMin">
              <el-input-number 
                v-model="configForm.buyRelativeDisplacementMin" 
                :step="0.01" 
                :precision="3"
                placeholder="5%"
                class="w-full"
              />
              <div class="form-help">相对位移 Δ/d，通常 > 5%</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="连续确认天数" prop="buyConsecutiveDays">
          <el-input-number 
            v-model="configForm.buyConsecutiveDays" 
            :min="1" 
            :max="10"
            placeholder="3天"
            class="w-full"
          />
          <div class="form-help">信号连续确认的天数，提高可靠性</div>
        </el-form-item>

        <!-- 卖出条件配置 -->
        <el-divider content-position="left">
          <el-icon><Warning /></el-icon>
          卖出条件配置
        </el-divider>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="乖离率最大值" prop="sellBiasMax">
              <el-input-number 
                v-model="configForm.sellBiasMax" 
                :step="0.01" 
                :precision="3"
                placeholder="8%"
                class="w-full"
              />
              <div class="form-help">超买信号，乖离率 > 8% 时卖出</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="即时偏离度最大值" prop="sellInstantDeviationMax">
              <el-input-number 
                v-model="configForm.sellInstantDeviationMax" 
                :step="0.01" 
                :precision="3"
                placeholder="5%"
                class="w-full"
              />
              <div class="form-help">价格偏离度过大时的卖出信号</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="价涨量缩背离" prop="sellPriceVolumeDivergence">
          <el-switch v-model="configForm.sellPriceVolumeDivergence" />
          <div class="form-help">检测价格上涨但成交量下降的背离信号</div>
        </el-form-item>

        <!-- 风控参数配置 -->
        <el-divider content-position="left">
          <el-icon><Lock /></el-icon>
          风险控制配置
        </el-divider>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="止损比例" prop="stopLoss">
              <el-input-number 
                v-model="configForm.stopLoss" 
                :step="0.01" 
                :precision="3"
                :max="0"
                placeholder="-10%"
                class="w-full"
              />
              <div class="form-help">最大亏损比例，建议 -5% 到 -15%</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="止盈比例" prop="takeProfit">
              <el-input-number 
                v-model="configForm.takeProfit" 
                :step="0.01" 
                :precision="3"
                :min="0"
                placeholder="20%"
                class="w-full"
              />
              <div class="form-help">目标盈利比例，建议 15% 到 30%</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最大仓位比例" prop="maxPositionSize">
              <el-input-number 
                v-model="configForm.maxPositionSize" 
                :step="0.01" 
                :precision="3"
                :min="0.01"
                :max="1"
                placeholder="10%"
                class="w-full"
              />
              <div class="form-help">单只股票最大仓位，建议 5% 到 20%</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大持有天数" prop="maxHoldingDays">
              <el-input-number 
                v-model="configForm.maxHoldingDays" 
                :min="1" 
                :max="365"
                placeholder="30天"
                class="w-full"
              />
              <div class="form-help">避免长期套牢，建议 20 到 60 天</div>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 高级配置 -->
        <el-divider content-position="left">
          <el-icon><Tools /></el-icon>
          高级配置
        </el-divider>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="信号强度阈值" prop="signalStrengthThreshold">
              <el-slider
                v-model="configForm.signalStrengthThreshold"
                :min="0.1"
                :max="1.0"
                :step="0.1"
                show-stops
                show-input
              />
              <div class="form-help">信号强度过滤阈值，越高越严格</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="风险等级" prop="riskLevel">
              <el-select v-model="configForm.riskLevel" placeholder="选择风险等级" class="w-full">
                <el-option label="保守" value="conservative" />
                <el-option label="平衡" value="balanced" />
                <el-option label="激进" value="aggressive" />
              </el-select>
              <div class="form-help">影响整体参数的风险偏好设置</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="启用动态调整" prop="enableDynamicAdjustment">
          <el-switch v-model="configForm.enableDynamicAdjustment" />
          <div class="form-help">根据市场环境自动调整参数</div>
        </el-form-item>

        <!-- 乖离率动态调整配置 -->
        <el-divider content-position="left">
          <el-icon><TrendCharts /></el-icon>
          乖离率动态调整配置
        </el-divider>

        <el-form-item label="启用动态乖离率调整" prop="enableDynamicBiasAdjustment">
          <el-switch v-model="configForm.enableDynamicBiasAdjustment" />
          <div class="form-help">根据市场波动率和股票特性动态调整乖离率阈值</div>
        </el-form-item>

        <el-collapse v-model="biasConfigCollapse" v-if="configForm.enableDynamicBiasAdjustment">
          <el-collapse-item title="市场波动率阈值配置" name="volatility">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="高波动阈值" prop="biasVolatilityHigh">
                  <el-input-number 
                    v-model="configForm.biasVolatilityHigh" 
                    :step="0.01" 
                    :precision="2"
                    :min="0.1"
                    placeholder="20%"
                    class="w-full"
                  />
                  <div class="form-help">波动率 > 此值时，buy_bias_min = 3%</div>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="中波动阈值" prop="biasVolatilityMedium">
                  <el-input-number 
                    v-model="configForm.biasVolatilityMedium" 
                    :step="0.01" 
                    :precision="2"
                    :min="0.05"
                    placeholder="10%"
                    class="w-full"
                  />
                  <div class="form-help">10% < 波动率 <= 20%，buy_bias_min = 2%</div>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="低波动阈值" prop="biasVolatilityLow">
                  <el-input-number 
                    v-model="configForm.biasVolatilityLow" 
                    :step="0.01" 
                    :precision="2"
                    :min="0.01"
                    placeholder="10%"
                    class="w-full"
                  />
                  <div class="form-help">波动率 <= 10%，buy_bias_min = 1%</div>
                </el-form-item>
              </el-col>
            </el-row>
          </el-collapse-item>

          <el-collapse-item title="价格区间调整规则" name="priceRange">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="低价股阈值" prop="biasLowPriceThreshold">
                  <el-input-number 
                    v-model="configForm.biasLowPriceThreshold" 
                    :step="1" 
                    :precision="0"
                    :min="1"
                    placeholder="10元"
                    class="w-full"
                  />
                  <div class="form-help">价格 < 此值时，buy_bias_min 放宽 +0.5%</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="高价股阈值" prop="biasHighPriceThreshold">
                  <el-input-number 
                    v-model="configForm.biasHighPriceThreshold" 
                    :step="1" 
                    :precision="0"
                    :min="10"
                    placeholder="50元"
                    class="w-full"
                  />
                  <div class="form-help">价格 > 此值时，buy_bias_min 收紧 -0.5%</div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="低价股调整幅度" prop="biasLowPriceAdjustment">
                  <el-input-number 
                    v-model="configForm.biasLowPriceAdjustment" 
                    :step="0.001" 
                    :precision="3"
                    :min="0"
                    placeholder="0.005"
                    class="w-full"
                  />
                  <div class="form-help">低价股buy_bias_min调整幅度（+）</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="高价股调整幅度" prop="biasHighPriceAdjustment">
                  <el-input-number 
                    v-model="configForm.biasHighPriceAdjustment" 
                    :step="0.001" 
                    :precision="3"
                    :min="0"
                    placeholder="0.005"
                    class="w-full"
                  />
                  <div class="form-help">高价股buy_bias_min调整幅度（-）</div>
                </el-form-item>
              </el-col>
            </el-row>
          </el-collapse-item>

          <el-collapse-item title="Bias历史分布配置" name="biasDistribution">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="历史分位数下限" prop="biasPercentileLower">
                  <el-input-number 
                    v-model="configForm.biasPercentileLower" 
                    :step="1" 
                    :precision="0"
                    :min="0"
                    :max="100"
                    placeholder="20"
                    class="w-full"
                  />
                  <div class="form-help">当前bias处于历史分位数下限（%）</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="历史分位数上限" prop="biasPercentileUpper">
                  <el-input-number 
                    v-model="configForm.biasPercentileUpper" 
                    :step="1" 
                    :precision="0"
                    :min="0"
                    :max="100"
                    placeholder="80"
                    class="w-full"
                  />
                  <div class="form-help">当前bias处于历史分位数上限（%）</div>
                </el-form-item>
              </el-col>
            </el-row>
            <div class="form-help">bias在[下限, 上限]区间内视为合理</div>
          </el-collapse-item>

          <el-collapse-item title="卖出Bias动态调整" name="sellBiasDynamic">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="高盈利阈值" prop="biasHighProfitThreshold">
                  <el-input-number 
                    v-model="configForm.biasHighProfitThreshold" 
                    :step="0.01" 
                    :precision="2"
                    :min="0.1"
                    placeholder="0.20"
                    class="w-full"
                  />
                  <div class="form-help">盈利 > 20%时，sell_bias_max = 20%</div>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="中盈利阈值" prop="biasMediumProfitThreshold">
                  <el-input-number 
                    v-model="configForm.biasMediumProfitThreshold" 
                    :step="0.01" 
                    :precision="2"
                    :min="0.05"
                    placeholder="0.10"
                    class="w-full"
                  />
                  <div class="form-help">10% < 盈利 <= 20%，sell_bias_max = 15%</div>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="低盈利阈值" prop="biasLowProfitThreshold">
                  <el-input-number 
                    v-model="configForm.biasLowProfitThreshold" 
                    :step="0.01" 
                    :precision="2"
                    :min="0"
                    placeholder="0.10"
                    class="w-full"
                  />
                  <div class="form-help">盈利 < 10%时，sell_bias_max = 10%</div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="短期持仓阈值" prop="biasShortHoldingDays">
                  <el-input-number 
                    v-model="configForm.biasShortHoldingDays" 
                    :step="1" 
                    :precision="0"
                    :min="1"
                    placeholder="10天"
                    class="w-full"
                  />
                  <div class="form-help">持仓 < 此天数时，sell_bias_max 收紧 -2%</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="长期持仓阈值" prop="biasLongHoldingDays">
                  <el-input-number 
                    v-model="configForm.biasLongHoldingDays" 
                    :step="1" 
                    :precision="0"
                    :min="10"
                    placeholder="30天"
                    class="w-full"
                  />
                  <div class="form-help">持仓 > 此天数时，sell_bias_max 放宽 +2%</div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="Bias趋势判断天数" prop="biasTrendDays">
              <el-input-number 
                v-model="configForm.biasTrendDays" 
                :step="1" 
                :precision="0"
                :min="1"
                :max="10"
                placeholder="3天"
                class="w-full"
              />
              <div class="form-help">bias连续N天扩大且超过阈值时触发卖出</div>
            </el-form-item>
          </el-collapse-item>
        </el-collapse>

        <!-- 价格维度增强配置 -->
        <el-divider content-position="left">
          <el-icon><TrendCharts /></el-icon>
          价格维度增强配置
        </el-divider>

        <el-form-item label="启用价格趋势持续性验证" prop="enablePriceTrendPersistence">
          <el-switch v-model="configForm.enablePriceTrendPersistence" />
          <div class="form-help">验证价格是否持续向上（最近5天、10天趋势斜率）</div>
        </el-form-item>

        <el-collapse v-model="priceConfigCollapse" v-if="configForm.enablePriceTrendPersistence">
          <el-collapse-item title="趋势持续性参数" name="trendParams">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="短期趋势天数" prop="priceTrendShortDays">
                  <el-input-number 
                    v-model="configForm.priceTrendShortDays" 
                    :step="1" 
                    :precision="0"
                    :min="3"
                    :max="10"
                    placeholder="5天"
                    class="w-full"
                  />
                  <div class="form-help">计算短期趋势斜率的天数</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="长期趋势天数" prop="priceTrendLongDays">
                  <el-input-number 
                    v-model="configForm.priceTrendLongDays" 
                    :step="1" 
                    :precision="0"
                    :min="5"
                    :max="20"
                    placeholder="10天"
                    class="w-full"
                  />
                  <div class="form-help">计算长期趋势斜率的天数</div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="最大回撤阈值" prop="priceMaxDrawdownThreshold">
              <el-input-number 
                v-model="configForm.priceMaxDrawdownThreshold" 
                :step="0.01" 
                :precision="2"
                :min="0.05"
                :max="0.30"
                placeholder="0.10"
                class="w-full"
              />
              <div class="form-help">价格回撤幅度 < 此值时通过验证（10%）</div>
            </el-form-item>
          </el-collapse-item>
        </el-collapse>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="价格波动率阈值" prop="priceVolatilityThreshold">
              <el-input-number 
                v-model="configForm.priceVolatilityThreshold" 
                :step="0.01" 
                :precision="2"
                :min="0.05"
                :max="0.30"
                placeholder="0.15"
                class="w-full"
              />
              <div class="form-help">20天标准差/均值，波动率 < 15% 排除异常波动</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="幅度系数下限" prop="amplitudeRatioMin">
              <el-input-number 
                v-model="configForm.amplitudeRatioMin" 
                :step="0.001" 
                :precision="3"
                :min="0.005"
                :max="0.05"
                placeholder="0.01"
                class="w-full"
              />
              <div class="form-help">幅度系数范围下限（1%）</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="幅度系数上限" prop="amplitudeRatioMax">
          <el-input-number 
            v-model="configForm.amplitudeRatioMax" 
            :step="0.01" 
            :precision="2"
            :min="0.10"
            :max="0.50"
            placeholder="0.30"
            class="w-full"
          />
          <div class="form-help">幅度系数范围上限（30%）</div>
        </el-form-item>

        <!-- 频率维度增强配置 -->
        <el-divider content-position="left">
          <el-icon><DataAnalysis /></el-icon>
          频率维度增强配置
        </el-divider>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最低上涨天数" prop="frequencyMinRisingDays">
              <el-input-number 
                v-model="configForm.frequencyMinRisingDays" 
                :step="1" 
                :precision="0"
                :min="8"
                :max="15"
                placeholder="10天"
                class="w-full"
              />
              <div class="form-help">Z >= 10（20天中占50%）</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="上涨天数优势" prop="frequencyRisingDaysAdvantage">
              <el-input-number 
                v-model="configForm.frequencyRisingDaysAdvantage" 
                :step="1" 
                :precision="0"
                :min="1"
                :max="10"
                placeholder="3天"
                class="w-full"
              />
              <div class="form-help">Z > F + N（默认N=3）</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="启用上涨集中度分析" prop="enableRisingConcentration">
              <el-switch v-model="configForm.enableRisingConcentration" />
              <div class="form-help">分析上涨天数是否集中在后期</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用虚假繁荣检测增强" prop="enableFalseProsperityEnhancement">
              <el-switch v-model="configForm.enableFalseProsperityEnhancement" />
              <div class="form-help">检查连续2-3天的异常涨幅</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-collapse v-model="frequencyConfigCollapse" v-if="configForm.enableFalseProsperityEnhancement">
          <el-collapse-item title="虚假繁荣检测参数" name="falseProsperity">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="连续异常涨幅阈值" prop="falseProsperityConsecutiveThreshold">
                  <el-input-number 
                    v-model="configForm.falseProsperityConsecutiveThreshold" 
                    :step="0.01" 
                    :precision="2"
                    :min="0.02"
                    :max="0.10"
                    placeholder="0.03"
                    class="w-full"
                  />
                  <div class="form-help">连续涨幅 > 3% 视为异常</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="异常涨幅天数" prop="falseProsperityDays">
                  <el-input-number 
                    v-model="configForm.falseProsperityDays" 
                    :step="1" 
                    :precision="0"
                    :min="2"
                    :max="5"
                    placeholder="3天"
                    class="w-full"
                  />
                  <div class="form-help">检查连续N天的异常涨幅</div>
                </el-form-item>
              </el-col>
            </el-row>
          </el-collapse-item>
        </el-collapse>

        <el-form-item label="上涨持续性验证天数" prop="frequencyPersistenceDays">
          <el-input-number 
            v-model="configForm.frequencyPersistenceDays" 
            :step="1" 
            :precision="0"
            :min="5"
            :max="15"
            placeholder="10天"
            class="w-full"
          />
          <div class="form-help">最近N天中上涨天数 >= 6</div>
        </el-form-item>

        <!-- 成交量维度增强配置 -->
        <el-divider content-position="left">
          <el-icon><TrendCharts /></el-icon>
          成交量维度增强配置
        </el-divider>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="连续放量天数要求" prop="volumeConsecutiveDays">
              <el-input-number 
                v-model="configForm.volumeConsecutiveDays" 
                :step="1" 
                :precision="0"
                :min="1"
                :max="5"
                placeholder="3天"
                class="w-full"
              />
              <div class="form-help">要求连续N天成交量放大</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用成交量趋势持续性验证" prop="enableVolumeTrendPersistence">
              <el-switch v-model="configForm.enableVolumeTrendPersistence" />
              <div class="form-help">验证成交量放大趋势的持续性</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-collapse v-model="volumeConfigCollapse" v-if="configForm.enableVolumeTrendPersistence">
          <el-collapse-item title="成交量趋势持续性参数" name="volumePersistence">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="验证天数" prop="volumePersistenceDays">
                  <el-input-number 
                    v-model="configForm.volumePersistenceDays" 
                    :step="1" 
                    :precision="0"
                    :min="3"
                    :max="10"
                    placeholder="5天"
                    class="w-full"
                  />
                  <div class="form-help">最近N天中至少有N/2天成交量>20日均量</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="放大天数占比阈值" prop="volumeIncreaseRatioThreshold">
                  <el-input-number 
                    v-model="configForm.volumeIncreaseRatioThreshold" 
                    :step="0.01" 
                    :precision="2"
                    :min="0.50"
                    :max="1.0"
                    placeholder="0.60"
                    class="w-full"
                  />
                  <div class="form-help">成交量放大天数占比 >= 60%</div>
                </el-form-item>
              </el-col>
            </el-row>
          </el-collapse-item>
        </el-collapse>

        <el-form-item label="量价相关系数阈值" prop="volumePriceCorrelationThreshold">
          <el-input-number 
            v-model="configForm.volumePriceCorrelationThreshold" 
            :step="0.1" 
            :precision="1"
            :min="0.3"
            :max="0.9"
            placeholder="0.5"
            class="w-full"
          />
          <div class="form-help">价格变化与成交量变化的相关系数 > 0.5</div>
        </el-form-item>

        <!-- 信号质量分级配置 -->
        <el-divider content-position="left">
          <el-icon><DataAnalysis /></el-icon>
          信号质量分级配置
        </el-divider>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="高质量信号阈值" prop="signalQualityHighThreshold">
              <el-input-number 
                v-model="configForm.signalQualityHighThreshold" 
                :step="0.05" 
                :precision="2"
                :min="0.7"
                :max="1.0"
                placeholder="0.85"
                class="w-full"
              />
              <div class="form-help">所有维度得分 > 0.8，共振强度 > 0.85</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="中等质量信号阈值" prop="signalQualityMediumThreshold">
              <el-input-number 
                v-model="configForm.signalQualityMediumThreshold" 
                :step="0.05" 
                :precision="2"
                :min="0.5"
                :max="0.9"
                placeholder="0.70"
                class="w-full"
              />
              <div class="form-help">所有维度得分 > 0.6，共振强度 > 0.7</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="维度得分下限" prop="signalQualityDimensionMin">
              <el-input-number 
                v-model="configForm.signalQualityDimensionMin" 
                :step="0.05" 
                :precision="2"
                :min="0.5"
                :max="0.9"
                placeholder="0.60"
                class="w-full"
              />
              <div class="form-help">中等质量信号要求的最低维度得分</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">信号强度权重配置</el-divider>

        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="Bias权重" prop="signalWeightBias">
              <el-input-number 
                v-model="configForm.signalWeightBias" 
                :step="0.01" 
                :precision="2"
                :min="0"
                :max="1"
                placeholder="0.10"
                class="w-full"
              />
              <div class="form-help">乖离率得分权重（10%）</div>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="价格权重" prop="signalWeightPrice">
              <el-input-number 
                v-model="configForm.signalWeightPrice" 
                :step="0.01" 
                :precision="2"
                :min="0"
                :max="1"
                placeholder="0.30"
                class="w-full"
              />
              <div class="form-help">价格维度权重</div>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="频率权重" prop="signalWeightFrequency">
              <el-input-number 
                v-model="configForm.signalWeightFrequency" 
                :step="0.01" 
                :precision="2"
                :min="0"
                :max="1"
                placeholder="0.30"
                class="w-full"
              />
              <div class="form-help">频率维度权重</div>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="成交量权重" prop="signalWeightVolume">
              <el-input-number 
                v-model="configForm.signalWeightVolume" 
                :step="0.01" 
                :precision="2"
                :min="0"
                :max="1"
                placeholder="0.30"
                class="w-full"
              />
              <div class="form-help">成交量维度权重</div>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 操作按钮 -->
        <el-form-item>
          <div class="form-actions">
            <el-button 
              type="primary" 
              @click="saveConfig" 
              :loading="saving"
              size="large"
            >
              保存配置
            </el-button>
            <el-button @click="resetConfig" size="large">
              重置默认
            </el-button>
            <el-button @click="loadConfig" size="large">
              重新加载
            </el-button>
            <el-button 
              type="success" 
              @click="testConfig" 
              :loading="testing"
              size="large"
            >
              测试配置
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 配置历史 -->
    <el-card class="config-history-card" header="配置历史">
      <el-table :data="configHistory" stripe>
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column prop="createdBy" label="创建者" width="120" />
        <el-table-column prop="createdAt" label="创建时间" width="160">
          <template #default="scope">
            {{ formatDateTime(scope.row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column prop="isActive" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.isActive ? 'success' : 'info'">
              {{ scope.row.isActive ? '当前' : '历史' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button 
              size="small" 
              @click="loadHistoryConfig(scope.row)"
              :disabled="scope.row.isActive"
            >
              加载
            </el-button>
            <el-button 
              size="small" 
              type="danger" 
              @click="deleteHistoryConfig(scope.row)"
              :disabled="scope.row.isActive"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, inject } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Setting, 
  DataAnalysis, 
  TrendCharts, 
  Warning, 
  Lock, 
  Tools 
} from '@element-plus/icons-vue'

// 类型定义
interface PVRFSApi {
  getStrategyConfig(): Promise<any>
  saveStrategyConfig(config: any): Promise<any>
  testStrategyConfig(config: any): Promise<any>
  getConfigHistory(): Promise<any>
  deleteConfigHistory(configId: string): Promise<void>
}

// 注入服务
const pvfrsApi = inject('pvfrsApi') as PVRFSApi

// 响应式数据
const configFormRef = ref()
const saving = ref(false)
const testing = ref(false)

// 当前配置概览
const currentConfig = reactive({
  version: '',
  updatedAt: '',
  isActive: true,
  buySignalStrength: 0,
  sellSignalStrength: 0,
  riskLevel: 'balanced',
  winRate: 0,
  avgReturn: 0,
  maxDrawdown: 0
})

// 配置表单
const configForm = reactive({
  buyMacroDisplacementMin: 0,
  buyInstantDeviationMin: 0,
  buyRisingDaysAdvantage: true,
  buyEfficiencyMin: 0,
  buyBiasMin: 0.02,
  buyRelativeDisplacementMin: 0.05,
  buyConsecutiveDays: 3,
  sellBiasMax: 0.08,
  sellInstantDeviationMax: 0.05,
  sellPriceVolumeDivergence: true,
  stopLoss: -0.1,
  takeProfit: 0.2,
  maxPositionSize: 0.1,
  maxHoldingDays: 30,
  signalStrengthThreshold: 0.7,
  riskLevel: 'balanced',
  enableDynamicAdjustment: false,
  // 乖离率动态调整配置
  enableDynamicBiasAdjustment: false,
  biasVolatilityHigh: 0.20,
  biasVolatilityMedium: 0.10,
  biasVolatilityLow: 0.10,
  biasLowPriceThreshold: 10,
  biasHighPriceThreshold: 50,
  biasLowPriceAdjustment: 0.005,
  biasHighPriceAdjustment: 0.005,
  biasPercentileLower: 20,
  biasPercentileUpper: 80,
  biasHighProfitThreshold: 0.20,
  biasMediumProfitThreshold: 0.10,
  biasLowProfitThreshold: 0.10,
  biasShortHoldingDays: 10,
  biasLongHoldingDays: 30,
  biasTrendDays: 3,
  // 价格维度增强配置
  enablePriceTrendPersistence: false,
  priceTrendShortDays: 5,
  priceTrendLongDays: 10,
  priceMaxDrawdownThreshold: 0.10,
  priceVolatilityThreshold: 0.15,
  amplitudeRatioMin: 0.01,
  amplitudeRatioMax: 0.30,
  // 频率维度增强配置
  frequencyMinRisingDays: 10,
  frequencyRisingDaysAdvantage: 3,
  enableRisingConcentration: false,
  enableFalseProsperityEnhancement: false,
  falseProsperityConsecutiveThreshold: 0.03,
  falseProsperityDays: 3,
  frequencyPersistenceDays: 10,
  // 成交量维度增强配置
  volumeConsecutiveDays: 3,
  enableVolumeTrendPersistence: false,
  volumePersistenceDays: 5,
  volumeIncreaseRatioThreshold: 0.60,
  volumePriceCorrelationThreshold: 0.5,
  // 信号质量分级配置
  signalQualityHighThreshold: 0.85,
  signalQualityMediumThreshold: 0.70,
  signalQualityDimensionMin: 0.60,
  signalWeightBias: 0.10,
  signalWeightPrice: 0.30,
  signalWeightFrequency: 0.30,
  signalWeightVolume: 0.30
})

// 配置折叠面板状态
const biasConfigCollapse = ref(['volatility', 'priceRange', 'biasDistribution', 'sellBiasDynamic'])
const priceConfigCollapse = ref(['trendParams'])
const frequencyConfigCollapse = ref(['falseProsperity'])
const volumeConfigCollapse = ref(['volumePersistence'])

// 表单验证规则
const configRules = {
  buyBiasMin: [
    { required: true, message: '请输入乖离率最小值', trigger: 'blur' }
  ],
  buyConsecutiveDays: [
    { required: true, message: '请输入连续确认天数', trigger: 'blur' }
  ],
  sellBiasMax: [
    { required: true, message: '请输入乖离率最大值', trigger: 'blur' }
  ],
  stopLoss: [
    { required: true, message: '请输入止损比例', trigger: 'blur' }
  ],
  takeProfit: [
    { required: true, message: '请输入止盈比例', trigger: 'blur' }
  ],
  maxPositionSize: [
    { required: true, message: '请输入最大仓位比例', trigger: 'blur' }
  ],
  maxHoldingDays: [
    { required: true, message: '请输入最大持有天数', trigger: 'blur' }
  ]
}

// 配置历史
const configHistory = ref([])

// 发射事件
const emit = defineEmits(['config-saved'])

// 方法
const loadConfig = async () => {
  try {
    const config = await pvfrsApi.getStrategyConfig()
    
    // 更新当前配置概览
    Object.assign(currentConfig, config.overview || {})
    
    // 更新表单数据
    Object.assign(configForm, config.parameters || {})
    
    ElMessage.success('配置加载成功')
  } catch (error) {
    ElMessage.error('配置加载失败')
    console.error('配置加载失败:', error)
  }
}

const saveConfig = async () => {
  try {
    await configFormRef.value.validate()
    
    saving.value = true
    
    await pvfrsApi.saveStrategyConfig({
      parameters: configForm,
      description: `配置更新于 ${new Date().toLocaleString()}`
    })
    
    ElMessage.success('配置保存成功')
    emit('config-saved', configForm)
    
    // 重新加载配置和历史
    await loadConfig()
    await loadConfigHistory()
    
  } catch (error) {
    ElMessage.error('配置保存失败')
    console.error('配置保存失败:', error)
  } finally {
    saving.value = false
  }
}

const resetConfig = async () => {
  try {
    await ElMessageBox.confirm('确定要重置为默认配置吗？', '确认重置', {
      type: 'warning'
    })
    
    // 重置为默认值
    Object.assign(configForm, {
      buyMacroDisplacementMin: 0,
      buyInstantDeviationMin: 0,
      buyRisingDaysAdvantage: true,
      buyEfficiencyMin: 0,
      buyBiasMin: 0.02,
      buyRelativeDisplacementMin: 0.05,
      buyConsecutiveDays: 3,
      sellBiasMax: 0.08,
      sellInstantDeviationMax: 0.05,
      sellPriceVolumeDivergence: true,
      stopLoss: -0.1,
      takeProfit: 0.2,
      maxPositionSize: 0.1,
      maxHoldingDays: 30,
      signalStrengthThreshold: 0.7,
      riskLevel: 'balanced',
      enableDynamicAdjustment: false,
      // 乖离率动态调整配置
      enableDynamicBiasAdjustment: false,
      biasVolatilityHigh: 0.20,
      biasVolatilityMedium: 0.10,
      biasVolatilityLow: 0.10,
      biasLowPriceThreshold: 10,
      biasHighPriceThreshold: 50,
      biasLowPriceAdjustment: 0.005,
      biasHighPriceAdjustment: 0.005,
      biasPercentileLower: 20,
      biasPercentileUpper: 80,
      biasHighProfitThreshold: 0.20,
      biasMediumProfitThreshold: 0.10,
      biasLowProfitThreshold: 0.10,
      biasShortHoldingDays: 10,
      biasLongHoldingDays: 30,
      biasTrendDays: 3,
      // 价格维度增强配置
      enablePriceTrendPersistence: false,
      priceTrendShortDays: 5,
      priceTrendLongDays: 10,
      priceMaxDrawdownThreshold: 0.10,
      priceVolatilityThreshold: 0.15,
      amplitudeRatioMin: 0.01,
      amplitudeRatioMax: 0.30,
      // 频率维度增强配置
      frequencyMinRisingDays: 10,
      frequencyRisingDaysAdvantage: 3,
      enableRisingConcentration: false,
      enableFalseProsperityEnhancement: false,
      falseProsperityConsecutiveThreshold: 0.03,
      falseProsperityDays: 3,
      frequencyPersistenceDays: 10,
      // 成交量维度增强配置
      volumeConsecutiveDays: 3,
      enableVolumeTrendPersistence: false,
      volumePersistenceDays: 5,
      volumeIncreaseRatioThreshold: 0.60,
      volumePriceCorrelationThreshold: 0.5,
      // 信号质量分级配置
      signalQualityHighThreshold: 0.85,
      signalQualityMediumThreshold: 0.70,
      signalQualityDimensionMin: 0.60,
      signalWeightBias: 0.10,
      signalWeightPrice: 0.30,
      signalWeightFrequency: 0.30,
      signalWeightVolume: 0.30
    })
    
    ElMessage.success('已重置为默认配置')
    
  } catch (error) {
    // 用户取消
  }
}

const testConfig = async () => {
  try {
    await configFormRef.value.validate()
    
    testing.value = true
    
    const result = await pvfrsApi.testStrategyConfig(configForm)
    
    ElMessageBox.alert(
      `测试结果：
      预期胜率: ${result.expectedWinRate}%
      预期收益: ${result.expectedReturn}%
      风险评级: ${result.riskRating}
      建议: ${result.recommendation}`,
      '配置测试结果',
      { type: 'info' }
    )
    
  } catch (error) {
    ElMessage.error('配置测试失败')
    console.error('配置测试失败:', error)
  } finally {
    testing.value = false
  }
}

const loadConfigHistory = async () => {
  try {
    const history = await pvfrsApi.getConfigHistory()
    configHistory.value = history || []
  } catch (error) {
    console.error('获取配置历史失败:', error)
  }
}

const loadHistoryConfig = async (historyConfig: any) => {
  try {
    await ElMessageBox.confirm('确定要加载这个历史配置吗？当前配置将被覆盖。', '确认加载', {
      type: 'warning'
    })
    
    Object.assign(configForm, historyConfig.parameters || {})
    ElMessage.success('历史配置已加载')
    
  } catch (error) {
    // 用户取消
  }
}

const deleteHistoryConfig = async (historyConfig: any) => {
  try {
    await ElMessageBox.confirm('确定要删除这个历史配置吗？', '确认删除', {
      type: 'warning'
    })
    
    await pvfrsApi.deleteConfigHistory(historyConfig.id)
    ElMessage.success('历史配置已删除')
    await loadConfigHistory()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除历史配置失败')
    }
  }
}

// 辅助方法
const getRiskLevelType = (level: string): "primary" | "success" | "warning" | "info" | "danger" => {
  const types: Record<string, "primary" | "success" | "warning" | "info" | "danger"> = {
    conservative: 'success',
    balanced: 'warning',
    aggressive: 'danger'
  }
  return types[level as keyof typeof types] || 'info'
}

const getRiskLevelLabel = (level: string): string => {
  const labels: Record<string, string> = {
    conservative: '保守',
    balanced: '平衡',
    aggressive: '激进'
  }
  return labels[level as keyof typeof labels] || level
}

const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString()
}

// 暴露方法给父组件
defineExpose({
  loadConfig
})

// 生命周期
onMounted(() => {
  loadConfig()
  loadConfigHistory()
})
</script>

<style scoped lang="postcss">
.strategy-configuration {
  @apply space-y-6;
}

.config-overview {
  @apply mb-6;
}

.overview-card {
  @apply h-full shadow-sm;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.overview-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.card-header {
  @apply flex items-center p-4 border-b border-gray-200;
}

.card-icon {
  @apply mr-2 text-blue-600;
  font-size: 20px;
}

.card-title {
  @apply font-semibold text-gray-900;
}

.card-content {
  @apply p-4 space-y-3;
}

.config-item {
  @apply flex justify-between items-center;
}

.config-label {
  @apply text-sm text-gray-600;
}

.config-value {
  @apply font-medium text-gray-900;
}

.config-form-card {
  @apply shadow-sm;
}

.config-form {
  @apply max-w-none;
}

.form-help {
  @apply text-xs text-gray-500 mt-1;
}

.form-actions {
  @apply flex gap-4 justify-center pt-6;
}

.config-history-card {
  @apply shadow-sm;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .config-overview :deep(.el-col) {
    @apply mb-4;
  }
  
  .form-actions {
    @apply flex-wrap justify-center;
  }
}

@media (max-width: 768px) {
  .card-content {
    @apply p-3 space-y-2;
  }
  
  .config-item {
    @apply flex-col items-start gap-1;
  }
  
  .config-form {
    :deep(.el-form-item__label) {
      @apply text-sm;
    }
  }
  
  .form-actions {
    @apply flex-col;
  }
  
  .form-actions .el-button {
    @apply w-full;
  }
}

/* 动画效果 */
.overview-card {
  animation: fadeInUp 0.6s ease-out;
}

.overview-card:nth-child(1) { animation-delay: 0.1s; }
.overview-card:nth-child(2) { animation-delay: 0.2s; }
.overview-card:nth-child(3) { animation-delay: 0.3s; }

.config-form-card {
  animation: slideInUp 0.6s ease-out 0.3s both;
}

.config-history-card {
  animation: slideInUp 0.6s ease-out 0.5s both;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>