<template>
  <el-collapse v-model="openPanels" class="cupb-rules-panel">
    <el-collapse-item name="rules">
      <template #title>
        <span class="rules-title">等级 / 量价 判定规则</span>
        <span class="rules-sub">（默认配置；可在策略配置 JSON 的 volume / pattern 中调整阈值）</span>
      </template>

      <div class="rules-body">
        <section class="rules-section">
          <h4 class="rules-heading">量价分 <code>volume_score</code></h4>
          <p class="rules-desc">取值范围 <strong>0～4</strong>，为下列四项量价检查中通过项数之和（MA 默认 50 日）：</p>
          <el-table :data="volumeRules" size="small" border class="rules-table">
            <el-table-column prop="key" label="检查项" width="100" />
            <el-table-column prop="rule" label="默认判定条件" min-width="280" />
            <el-table-column prop="meaning" label="含义" min-width="160" />
          </el-table>
          <p class="rules-note">未确认突破时「突破放量」项按算法默认处理；可在结果 <code>detail.volume_flags</code> 查看各项是否通过。</p>
        </section>

        <section class="rules-section">
          <h4 class="rules-heading">等级 <code>grade</code></h4>
          <p class="rules-desc">取值 <strong>A / B / C / X</strong>（扫描结果通常不含 X，失效形态已被过滤）：</p>
          <el-table :data="gradeRules" size="small" border class="rules-table">
            <el-table-column prop="grade" label="等级" width="72" align="center">
              <template #default="{ row }">
                <el-tag :type="row.tagType" size="small">{{ row.grade }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="volumeRange" label="量价分" width="100" align="center" />
            <el-table-column prop="condition" label="判定条件" min-width="360" />
          </el-table>
          <p class="rules-note">
            <strong>延长基底 / 深杯</strong>：杯深 &gt;33%，或杯身 K 线数 ≥60 日等；此类形态若量价未四项全过，等级优先定为 C（即使量价分为 3）。
          </p>
        </section>
      </div>
    </el-collapse-item>
  </el-collapse>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const openPanels = ref<string[]>(['rules'])

const volumeRules = [
  {
    key: '杯底缩量',
    rule: '杯底日成交量 ≤ MA50 × 0.70',
    meaning: '底部交投干涸',
  },
  {
    key: '右侧放量',
    rule: '杯底 → 右沿区间至少 3 日成交量 > MA50',
    meaning: '右侧回升有资金参与',
  },
  {
    key: '柄部缩量',
    rule: '柄部均量 ≤ MA50 × 0.65',
    meaning: '柄部洗盘缩量',
  },
  {
    key: '突破放量',
    rule: '确认日成交量 ≥ MA50 × 1.40',
    meaning: '突破有效性（已确认时检验）',
  },
]

const gradeRules = [
  {
    grade: 'A',
    tagType: 'success' as const,
    volumeRange: '≥ 3',
    condition: '结构合格，且非「延长/深杯未全过量价」；量价分 ≥3',
  },
  {
    grade: 'B',
    tagType: 'primary' as const,
    volumeRange: '1～2',
    condition: '结构合格，量价分 1～2 项通过',
  },
  {
    grade: 'C',
    tagType: 'warning' as const,
    volumeRange: '0～3',
    condition: '延长型/深杯且量价未四项全过；或量价分 0 项通过',
  },
  {
    grade: 'X',
    tagType: 'info' as const,
    volumeRange: '—',
    condition: '形态失效或结构不合格（默认不出现在扫描列表）',
  },
]
</script>

<style scoped>
.cupb-rules-panel {
  margin-bottom: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
}
.cupb-rules-panel :deep(.el-collapse-item__header) {
  padding: 0 12px;
  background: #f8fafc;
  height: 42px;
  line-height: 42px;
}
.cupb-rules-panel :deep(.el-collapse-item__wrap) {
  background: #fff;
}
.cupb-rules-panel :deep(.el-collapse-item__content) {
  padding: 0 12px 12px;
}
.rules-title {
  font-weight: 600;
  color: #1e293b;
}
.rules-sub {
  margin-left: 8px;
  font-size: 12px;
  color: #64748b;
  font-weight: normal;
}
.rules-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.rules-section {
  min-width: 0;
}
.rules-heading {
  margin: 0 0 6px;
  font-size: 14px;
  color: #334155;
}
.rules-desc {
  margin: 0 0 8px;
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}
.rules-note {
  margin: 8px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.rules-table {
  width: 100%;
}
.rules-table :deep(.cell) {
  font-size: 12px;
  line-height: 1.45;
}
code {
  font-size: 12px;
  padding: 0 4px;
  background: #f1f5f9;
  border-radius: 4px;
}
</style>
