<template>
  <div class="eval-page">
    <h2 class="page-title">图表可视化</h2>
    <p class="page-desc">
      单次任务的雷达图为 Ragas、Judge 与运行时指标在条目上的均值归一化结果；柱状图为两次任务的均值对比（后端聚合接口示例：
      <code>GET /eval/tasks/:id/analytics</code>）。
    </p>

    <section class="card">
      <h3 class="card-title">单次任务 · 雷达图</h3>
      <div class="row">
        <label class="field">
          <span>评测任务</span>
          <select v-model="singleTaskId">
            <option value="">请选择已完成任务</option>
            <option v-for="t in chartableTasks" :key="'S-' + t.id" :value="t.id">
              {{ t.name }}（{{ t.passed_count }}/{{ t.failed_count }}）
            </option>
          </select>
        </label>
      </div>
      <p v-if="singleLoadError" class="err">{{ singleLoadError }}</p>
      <div v-if="singleLoading" class="hint">加载中…</div>
      <div v-else-if="singleTaskId && radarOption" class="chart-wrap">
        <VChart class="chart" :option="radarOption" autoresize />
        <p v-if="singleMeta.items_with_radar === 0" class="hint warn">
          暂无含 radar_json 的条目（任务完成后重新跑评测或检查 Ragas/Judge/API Key）。
        </p>
        <p v-else class="hint">
          基于 {{ singleMeta.items_with_radar }} 条结果的均值。
        </p>
      </div>
      <div v-else-if="singleTaskId && !radarOption" class="hint">无可用坐标轴数据。</div>
      <div v-else class="hint">请选择任务。</div>
    </section>

    <section class="card">
      <h3 class="card-title">双任务对比 · 柱状图</h3>
      <div class="compare-controls">
        <label class="field">
          <span>任务 A</span>
          <select v-model="compareLeft">
            <option value="">请选择</option>
            <option v-for="t in chartableTasks" :key="'CL-' + t.id" :value="t.id">{{ t.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>任务 B</span>
          <select v-model="compareRight">
            <option value="">请选择</option>
            <option v-for="t in chartableTasks" :key="'CR-' + t.id" :value="t.id">{{ t.name }}</option>
          </select>
        </label>
        <button type="button" class="btn btn-primary" :disabled="!canCompare || compareLoading" @click="loadCompare">
          {{ compareLoading ? '加载中…' : '加载对比' }}
        </button>
      </div>
      <p v-if="compareLoadError" class="err">{{ compareLoadError }}</p>
      <div v-if="compareData && barOption" class="chart-wrap tall">
        <VChart class="chart" :option="barOption" autoresize />
      </div>
      <div v-else class="hint">选择两个不同任务后点击「加载对比」。</div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart, BarChart } from 'echarts/charts'
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
  token_efficiency: 'Token 效率',
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
    series: [
      {
        type: 'radar',
        data: [{ value: vals, name: '均值', areaStyle: { opacity: 0.12 } }],
        symbolSize: 6,
        lineStyle: { width: 2 }
      }
    ]
  }
})

const barOption = computed(() => {
  const d = compareData.value
  if (!d?.left || !d?.right) return null
  const L = d.left.radar_mean || {}
  const R = d.right.radar_mean || {}
  const axes = d.left.radar_axes?.length ? d.left.radar_axes : [...new Set([...Object.keys(L), ...Object.keys(R)])]
  if (!axes.length) return null
  const cats = axes.map(k => LABEL_MAP[k] || k)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['任务 A', '任务 B'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '14%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: cats,
      axisLabel: { rotate: 28, fontSize: 11 }
    },
    yAxis: { type: 'value', min: 0, max: 1, splitNumber: 5 },
    series: [
      {
        name: '任务 A',
        type: 'bar',
        data: axes.map(k => Number(L[k] ?? 0)),
        barGap: '12%',
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      },
      {
        name: '任务 B',
        type: 'bar',
        data: axes.map(k => Number(R[k] ?? 0)),
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      }
    ]
  }
})
</script>

<style scoped>
.eval-page {
  max-width: 980px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 6px;
}

.page-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 20px;
  line-height: 1.5;
}

.page-desc code {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-surface);
}

.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 18px 20px;
  margin-bottom: 20px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 14px;
}

.row {
  margin-bottom: 12px;
}

.compare-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: flex-end;
  margin-bottom: 12px;
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
