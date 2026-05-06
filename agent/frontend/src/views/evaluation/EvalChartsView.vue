<template>
  <div class="eval-page">
    <h2 class="page-title">图表可视化</h2>
    <p class="page-desc">
      多种图表从不同维度展示评测结果：雷达图汇总多维度均值、柱状图对比两任务指标、
      折线图追踪逐条通过情况、饼图展示安全风险分布。
    </p>

    <!-- 任务选择器 -->
    <section class="card">
      <div class="task-selectors">
        <label class="field">
          <span>单任务（雷达图 / 折线图 / 安全饼图）</span>
          <select v-model="singleTaskId">
            <option value="">请选择已完成任务</option>
            <option v-for="t in chartableTasks" :key="'S-' + t.id" :value="t.id">
              {{ t.name }}（{{ t.passed_count }}/{{ t.completed_items }}）
            </option>
          </select>
        </label>
        <div class="compare-fields">
          <label class="field">
            <span>对比任务 A</span>
            <select v-model="compareLeft">
              <option value="">请选择</option>
              <option v-for="t in chartableTasks" :key="'CL-' + t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </label>
          <label class="field">
            <span>对比任务 B</span>
            <select v-model="compareRight">
              <option value="">请选择</option>
              <option v-for="t in chartableTasks" :key="'CR-' + t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </label>
          <button type="button" class="btn btn-primary" :disabled="!canCompare || compareLoading" @click="loadCompare">
            {{ compareLoading ? '加载中…' : '加载对比' }}
          </button>
        </div>
      </div>
      <p v-if="singleLoadError" class="err">{{ singleLoadError }}</p>
      <p v-if="compareLoadError" class="err">{{ compareLoadError }}</p>
    </section>

    <!-- 雷达图 -->
    <section class="card" v-if="singleTaskId">
      <h3 class="card-title">单任务 · 多维度雷达图</h3>
      <div v-if="singleLoading" class="hint">加载中…</div>
      <div v-else-if="radarOption" class="chart-wrap">
        <VChart class="chart" :option="radarOption" autoresize />
        <p v-if="singleMeta.items_with_radar === 0" class="hint warn">
          暂无含 radar_json 的条目（检查 API Key 或重新运行任务）。
        </p>
        <p v-else class="hint">基于 {{ singleMeta.items_with_radar }} 条结果的均值（归一化到 0–1）。</p>
      </div>
      <div v-else class="hint">无可用坐标轴数据。</div>
    </section>

    <!-- 逐条通过折线图 -->
    <section class="card" v-if="singleTaskId">
      <h3 class="card-title">单任务 · 逐条通过情况折线图</h3>
      <div v-if="singleLoading" class="hint">加载中…</div>
      <div v-else-if="lineOption" class="chart-wrap">
        <VChart class="chart" :option="lineOption" autoresize />
      </div>
      <div v-else class="hint">暂无逐条数据。</div>
    </section>

    <!-- 安全风险分布饼图 -->
    <section class="card" v-if="singleTaskId">
      <h3 class="card-title">单任务 · 安全风险分布饼图</h3>
      <div v-if="singleLoading" class="hint">加载中…</div>
      <div v-else-if="pieOption" class="chart-wrap">
        <VChart class="chart chart-sm" :option="pieOption" autoresize />
      </div>
      <div v-else class="hint">暂无安全数据。</div>
    </section>

    <!-- 双任务柱状对比 -->
    <section class="card">
      <h3 class="card-title">双任务对比 · 多维度柱状图</h3>
      <div v-if="compareData && barOption" class="chart-wrap tall">
        <VChart class="chart" :option="barOption" autoresize />
      </div>
      <div v-else class="hint">选择两个不同任务后点击「加载对比」。</div>
    </section>

    <!-- 双任务性能对比 -->
    <section class="card" v-if="compareData">
      <h3 class="card-title">双任务对比 · 性能指标柱状图</h3>
      <div v-if="perfBarOption" class="chart-wrap">
        <VChart class="chart" :option="perfBarOption" autoresize />
      </div>
      <div v-else class="hint">无性能数据可展示。</div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart, BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { useEvaluationStore } from '../../stores/evaluation.js'
import { getEvalTaskAnalytics, getEvalCompareAnalytics } from '../../api/index.js'

use([
  CanvasRenderer,
  RadarChart,
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent
])

const LABEL_MAP = {
  answer_relevancy: '答复相关性',
  faithfulness: '忠实度',
  reasoning_quality: '推理质量',
  anti_hallucination: '抗幻觉',
  tool_success: '工具成功',
  token_efficiency: 'Token效率',
  security_hygiene: '代码安全'
}

const ev = useEvaluationStore()

const chartableTasks = computed(() =>
  ev.tasks.filter(t => t.status === 'completed' && (t.completed_items || 0) > 0)
)

const singleTaskId = ref('')
const singleAnalytics = ref(null)
const singleLoading = ref(false)
const singleLoadError = ref('')

const compareLeft = ref('')
const compareRight = ref('')
const compareData = ref(null)
const compareLoading = ref(false)
const compareLoadError = ref('')

const singleMeta = computed(() => ({
  items_with_radar: singleAnalytics.value?.items_with_radar ?? 0
}))

const canCompare = computed(
  () => compareLeft.value && compareRight.value && compareLeft.value !== compareRight.value
)

onMounted(() => ev.loadTasks())

watch(singleTaskId, async id => {
  singleAnalytics.value = null
  singleLoadError.value = ''
  if (!id) return
  singleLoading.value = true
  try {
    singleAnalytics.value = await getEvalTaskAnalytics(id)
  } catch (e) {
    singleLoadError.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    singleLoading.value = false
  }
})

async function loadCompare() {
  compareLoadError.value = ''
  compareData.value = null
  if (!canCompare.value) return
  compareLoading.value = true
  try {
    compareData.value = await getEvalCompareAnalytics(compareLeft.value, compareRight.value)
  } catch (e) {
    compareLoadError.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    compareLoading.value = false
  }
}

// 雷达图
const radarOption = computed(() => {
  const an = singleAnalytics.value
  if (!an) return null
  const axes = an.radar_axes?.length ? an.radar_axes : Object.keys(an.radar_mean || {})
  if (!axes.length) return null
  const m = an.radar_mean || {}
  const vals = axes.map(k => Number(m[k] ?? 0))
  const indicators = axes.map(k => ({ name: LABEL_MAP[k] || k, max: 1 }))
  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: indicators,
      center: ['50%', '54%'],
      radius: '58%',
      splitNumber: 4,
      axisName: { fontSize: 11 }
    },
    series: [{
      type: 'radar',
      data: [{ value: vals, name: '均值', areaStyle: { opacity: 0.15 } }],
      symbolSize: 6,
      lineStyle: { width: 2 }
    }]
  }
})

// 逐条折线图（通过=1，未通过=0）
const lineOption = computed(() => {
  const an = singleAnalytics.value
  if (!an?.items?.length) return null
  const items = an.items.slice().sort((a, b) => a.item_index - b.item_index)
  const xData = items.map(i => 'Item ' + i.item_index)
  const passData = items.map(i => i.passed === true ? 1 : i.passed === false ? 0 : null)
  const tokenData = items.map(i => i.runtime_metrics?.tokens_total ?? null)
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['通过(1=是,0=否)', 'Token总量'], bottom: 0 },
    grid: { left: '3%', right: '8%', top: '6%', bottom: '14%', containLabel: true },
    xAxis: {
      type: 'category',
      data: xData,
      axisLabel: { fontSize: 10, rotate: xData.length > 10 ? 30 : 0 }
    },
    yAxis: [
      { type: 'value', name: '通过', min: 0, max: 1, splitNumber: 2, position: 'left' },
      { type: 'value', name: 'Token', position: 'right', axisLabel: { fontSize: 10 } }
    ],
    series: [
      {
        name: '通过(1=是,0=否)',
        type: 'line',
        data: passData,
        step: 'end',
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 2 },
        itemStyle: { color: '#7ec8a0' }
      },
      {
        name: 'Token总量',
        type: 'line',
        yAxisIndex: 1,
        data: tokenData,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 1.5, type: 'dashed' },
        itemStyle: { color: '#a0b4d0' }
      }
    ]
  }
})

// 安全饼图
const pieOption = computed(() => {
  const m = singleAnalytics.value?.explicit_metrics?.security_band_counts
  if (!m) return null
  const data = [
    { value: m.low || 0, name: '低风险', itemStyle: { color: '#7ec8a0' } },
    { value: m.medium || 0, name: '中风险', itemStyle: { color: '#e0ba6c' } },
    { value: m.high || 0, name: '高风险', itemStyle: { color: '#d9706a' } },
    { value: m.unknown || 0, name: '未扫描', itemStyle: { color: '#666' } },
  ].filter(d => d.value > 0)
  if (!data.length) return null
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 条 ({d}%)' },
    legend: { bottom: 0, fontSize: 11 },
    series: [{
      type: 'pie',
      radius: ['36%', '65%'],
      center: ['50%', '44%'],
      data,
      label: { fontSize: 11 }
    }]
  }
})

// 柱状对比图（雷达维度）
const barOption = computed(() => {
  const d = compareData.value
  if (!d?.left || !d?.right) return null
  const L = d.left.radar_mean || {}
  const R = d.right.radar_mean || {}
  const axes = d.left.radar_axes?.length ? d.left.radar_axes : [...new Set([...Object.keys(L), ...Object.keys(R)])]
  if (!axes.length) return null
  const cats = axes.map(k => LABEL_MAP[k] || k)
  const nameA = ev.tasks.find(t => t.id === compareLeft.value)?.name || '任务 A'
  const nameB = ev.tasks.find(t => t.id === compareRight.value)?.name || '任务 B'
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: [nameA, nameB], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '14%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: cats,
      axisLabel: { rotate: 28, fontSize: 11 }
    },
    yAxis: { type: 'value', min: 0, max: 1, splitNumber: 5 },
    series: [
      {
        name: nameA,
        type: 'bar',
        data: axes.map(k => Number(L[k] ?? 0)),
        barGap: '12%',
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      },
      {
        name: nameB,
        type: 'bar',
        data: axes.map(k => Number(R[k] ?? 0)),
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      }
    ]
  }
})

// 性能指标对比柱状图
const perfBarOption = computed(() => {
  const d = compareData.value
  if (!d?.left?.explicit_metrics || !d?.right?.explicit_metrics) return null
  const lm = d.left.explicit_metrics
  const rm = d.right.explicit_metrics
  const nameA = ev.tasks.find(t => t.id === compareLeft.value)?.name || '任务 A'
  const nameB = ev.tasks.find(t => t.id === compareRight.value)?.name || '任务 B'

  const cats = ['条均Token', '条均LLM调用', '工具成功率(%)', '平均响应时间(s)']
  const aVals = [
    lm.tokens_avg_per_item ?? 0,
    lm.llm_calls_avg ?? 0,
    lm.tool_success_rate_avg != null ? lm.tool_success_rate_avg * 100 : 0,
    lm.response_time_avg_ms != null ? lm.response_time_avg_ms / 1000 : 0
  ]
  const bVals = [
    rm.tokens_avg_per_item ?? 0,
    rm.llm_calls_avg ?? 0,
    rm.tool_success_rate_avg != null ? rm.tool_success_rate_avg * 100 : 0,
    rm.response_time_avg_ms != null ? rm.response_time_avg_ms / 1000 : 0
  ]

  if (aVals.every(v => !v) && bVals.every(v => !v)) return null

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: [nameA, nameB], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '14%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: cats },
    yAxis: { type: 'value' },
    series: [
      {
        name: nameA,
        type: 'bar',
        data: aVals,
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      },
      {
        name: nameB,
        type: 'bar',
        data: bVals,
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      }
    ]
  }
})
</script>

<style scoped>
.eval-page {
  max-width: 980px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 6px;
}

.page-desc {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}

.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 18px 20px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 14px;
}

.task-selectors {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.compare-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: flex-end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 200px;
  flex: 1;
}

.field select {
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  padding: 8px 10px;
  border-radius: 8px;
}

.chart-wrap {
  margin-top: 8px;
}

.chart-wrap.tall .chart {
  height: 400px;
}

.chart {
  width: 100%;
  height: 340px;
}

.chart-sm {
  height: 280px;
}

.hint {
  font-size: 12px;
  color: var(--text-muted);
  padding: 8px 0;
}

.hint.warn {
  color: var(--warning);
}

.err {
  font-size: 12px;
  color: var(--danger);
  margin-bottom: 8px;
}

.btn {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  border: none;
  cursor: pointer;
  height: fit-content;
}

.btn-primary {
  background: var(--accent);
  color: var(--bg-primary);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
