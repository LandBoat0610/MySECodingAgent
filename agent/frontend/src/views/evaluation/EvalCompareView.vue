<template>
  <div class="eval-page">
    <h2 class="page-title">对比分析</h2>
    <p class="page-desc">
      选择两次已完成的评测任务，对其在多个维度（效果、性能、安全）进行对比。
      逐条结果按 <code>item_key</code> 对齐；若 key 不同则回退到序号对齐。
    </p>

    <div class="select-row">
      <label class="field">
        <span>基准任务（A）</span>
        <select v-model="leftId" @change="onSelectChange">
          <option value="">请选择</option>
          <option v-for="t in comparableTasks" :key="'L-' + t.id" :value="t.id">
            {{ t.name }}（{{ methodLabel(t.eval_method) }}，{{ t.passed_count }}/{{ t.completed_items }}）
          </option>
        </select>
      </label>
      <label class="field">
        <span>对照任务（B）</span>
        <select v-model="rightId" @change="onSelectChange">
          <option value="">请选择</option>
          <option v-for="t in comparableTasks" :key="'R-' + t.id" :value="t.id">
            {{ t.name }}（{{ methodLabel(t.eval_method) }}，{{ t.passed_count }}/{{ t.completed_items }}）
          </option>
        </select>
      </label>
      <button
        class="btn btn-primary"
        :disabled="!canCompare || loadingCompare"
        @click="doCompare"
      >
        {{ loadingCompare ? '加载中…' : '对比分析' }}
      </button>
    </div>

    <div v-if="compareErr" class="banner-error">{{ compareErr }}</div>

    <template v-if="compareData">
      <!-- 汇总对比卡片 -->
      <section class="card">
        <h3 class="card-title">汇总对比</h3>
        <div class="summary-grid">
          <div class="summary-col header-col">
            <div class="summary-cell label-cell">指标</div>
            <div class="summary-cell">任务通过率</div>
            <div class="summary-cell">Token 总量</div>
            <div class="summary-cell">条均 Token</div>
            <div class="summary-cell">工具成功率（均值）</div>
            <div class="summary-cell">平均响应时间</div>
            <div class="summary-cell">答复相关性（Ragas 均）</div>
            <div class="summary-cell">忠实度（Ragas 均）</div>
            <div class="summary-cell">推理质量（Judge 均）</div>
            <div class="summary-cell">幻觉严重度（Judge 均）</div>
            <div class="summary-cell">安全：高风险条数</div>
          </div>

          <div class="summary-col task-a">
            <div class="summary-cell label-cell task-a-head">A：{{ leftTask?.name }}</div>
            <div class="summary-cell">{{ leftPassRate }}</div>
            <div class="summary-cell">{{ fmtInt(compareData.left.explicit_metrics?.tokens_total_sum) }}</div>
            <div class="summary-cell">{{ fmtNum(compareData.left.explicit_metrics?.tokens_avg_per_item) }}</div>
            <div class="summary-cell">{{ fmtPct(compareData.left.explicit_metrics?.tool_success_rate_avg) }}</div>
            <div class="summary-cell">{{ fmtSec(compareData.left.explicit_metrics?.response_time_avg_ms) }}</div>
            <div class="summary-cell">{{ fmtNum(compareData.left.explicit_metrics?.ragas_answer_relevancy_avg, 3) }}</div>
            <div class="summary-cell">{{ fmtNum(compareData.left.explicit_metrics?.ragas_faithfulness_avg, 3) }}</div>
            <div class="summary-cell">{{ fmtScore10(compareData.left.explicit_metrics?.judge_reasoning_quality_avg) }}</div>
            <div class="summary-cell">{{ fmtScore10(compareData.left.explicit_metrics?.judge_hallucination_severity_avg) }}</div>
            <div class="summary-cell">{{ compareData.left.explicit_metrics?.security_band_counts?.high ?? '—' }}</div>
          </div>

          <div class="summary-col task-b">
            <div class="summary-cell label-cell task-b-head">B：{{ rightTask?.name }}</div>
            <div class="summary-cell">{{ rightPassRate }}</div>
            <div class="summary-cell">{{ fmtInt(compareData.right.explicit_metrics?.tokens_total_sum) }}</div>
            <div class="summary-cell">{{ fmtNum(compareData.right.explicit_metrics?.tokens_avg_per_item) }}</div>
            <div class="summary-cell">{{ fmtPct(compareData.right.explicit_metrics?.tool_success_rate_avg) }}</div>
            <div class="summary-cell">{{ fmtSec(compareData.right.explicit_metrics?.response_time_avg_ms) }}</div>
            <div class="summary-cell">{{ fmtNum(compareData.right.explicit_metrics?.ragas_answer_relevancy_avg, 3) }}</div>
            <div class="summary-cell">{{ fmtNum(compareData.right.explicit_metrics?.ragas_faithfulness_avg, 3) }}</div>
            <div class="summary-cell">{{ fmtScore10(compareData.right.explicit_metrics?.judge_reasoning_quality_avg) }}</div>
            <div class="summary-cell">{{ fmtScore10(compareData.right.explicit_metrics?.judge_hallucination_severity_avg) }}</div>
            <div class="summary-cell">{{ compareData.right.explicit_metrics?.security_band_counts?.high ?? '—' }}</div>
          </div>

          <div class="summary-col delta-col">
            <div class="summary-cell label-cell">Δ (B−A)</div>
            <div class="summary-cell"><span :class="deltaClass(deltaPassRate)">{{ deltaPassRate }}</span></div>
            <div class="summary-cell"><span :class="deltaClass(deltaTokens, true)">{{ deltaTokens }}</span></div>
            <div class="summary-cell"><span :class="deltaClass(deltaAvgToken, true)">{{ deltaAvgToken }}</span></div>
            <div class="summary-cell"><span :class="deltaClass(deltaToolRate)">{{ deltaToolRate }}</span></div>
            <div class="summary-cell"><span :class="deltaClass(deltaResponseTime, true)">{{ deltaResponseTime }}</span></div>
            <div class="summary-cell"><span :class="deltaClass(deltaRagasAR)">{{ deltaRagasAR }}</span></div>
            <div class="summary-cell"><span :class="deltaClass(deltaRagasFF)">{{ deltaRagasFF }}</span></div>
            <div class="summary-cell"><span :class="deltaClass(deltaJudgeRQ)">{{ deltaJudgeRQ }}</span></div>
            <div class="summary-cell"><span :class="deltaClass(deltaJudgeHS, true)">{{ deltaJudgeHS }}</span></div>
            <div class="summary-cell"><span :class="deltaClass(deltaHighRisk, true)">{{ deltaHighRisk }}</span></div>
          </div>
        </div>
      </section>

      <!-- 逐条对比 -->
      <section class="card">
        <h3 class="card-title">逐条对比（按 item_key 对齐）</h3>
        <p class="hint muted">共 {{ alignedRows.length }} 条；A/B 均有数据的条目以 key 对齐，仅一侧有数据的条目标记为「仅A」或「仅B」。</p>
        <div class="compare-table-wrap">
          <table class="compare-table">
            <thead>
              <tr>
                <th class="col-key">Key</th>
                <th>描述</th>
                <th class="col-pass">A 通过</th>
                <th class="col-metric">A Token</th>
                <th class="col-metric">A 耗时(s)</th>
                <th class="col-metric">A 推理</th>
                <th class="col-sep">|</th>
                <th class="col-pass">B 通过</th>
                <th class="col-metric">B Token</th>
                <th class="col-metric">B 耗时(s)</th>
                <th class="col-metric">B 推理</th>
                <th class="col-diff">结果变化</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in alignedRows"
                :key="row.key"
                :class="rowClass(row)"
              >
                <td class="mono small muted">{{ row.key }}</td>
                <td class="desc-cell">{{ row.desc }}</td>
                <td class="col-pass"><span :class="passClass(row.a?.passed)">{{ passSymbol(row.a?.passed) }}</span></td>
                <td class="mono small">{{ fmtInt(row.a?.runtime_metrics?.tokens_total) }}</td>
                <td class="mono small">{{ itemTime(row.a) }}</td>
                <td class="mono small">{{ row.a?.judge?.reasoning_quality != null ? row.a.judge.reasoning_quality + '/10' : '—' }}</td>
                <td class="col-sep muted">|</td>
                <td class="col-pass"><span :class="passClass(row.b?.passed)">{{ passSymbol(row.b?.passed) }}</span></td>
                <td class="mono small">{{ fmtInt(row.b?.runtime_metrics?.tokens_total) }}</td>
                <td class="mono small">{{ itemTime(row.b) }}</td>
                <td class="mono small">{{ row.b?.judge?.reasoning_quality != null ? row.b.judge.reasoning_quality + '/10' : '—' }}</td>
                <td class="col-diff">
                  <span v-if="row.a && row.b" :class="diffClass(row.a.passed, row.b.passed)">
                    {{ diffLabel(row.a.passed, row.b.passed) }}
                  </span>
                  <span v-else class="muted small">{{ row.a ? '仅A' : '仅B' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useEvaluationStore } from '../../stores/evaluation.js'
import { getEvalCompareAnalytics } from '../../api/index.js'

const ev = useEvaluationStore()

const leftId = ref('')
const rightId = ref('')
const compareData = ref(null)
const loadingCompare = ref(false)
const compareErr = ref('')

const comparableTasks = computed(() =>
  ev.tasks.filter(t => t.status === 'completed' && (t.completed_items || 0) > 0)
)

const canCompare = computed(() => leftId.value && rightId.value && leftId.value !== rightId.value)

const leftTask = computed(() => ev.tasks.find(t => t.id === leftId.value))
const rightTask = computed(() => ev.tasks.find(t => t.id === rightId.value))

onMounted(() => ev.loadTasks())

function onSelectChange() {
  compareData.value = null
  compareErr.value = ''
}

function methodLabel(m) {
  if (m === 'process') return '过程'
  if (m === 'combined') return '联合'
  return '结果'
}

async function doCompare() {
  if (!canCompare.value) return
  compareErr.value = ''
  compareData.value = null
  loadingCompare.value = true
  try {
    compareData.value = await getEvalCompareAnalytics(leftId.value, rightId.value)
  } catch (e) {
    compareErr.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loadingCompare.value = false
  }
}

// 汇总指标
const leftPassRate = computed(() => {
  const t = leftTask.value
  if (!t?.completed_items) return '—'
  return ((t.passed_count / t.completed_items) * 100).toFixed(1) + '%'
})
const rightPassRate = computed(() => {
  const t = rightTask.value
  if (!t?.completed_items) return '—'
  return ((t.passed_count / t.completed_items) * 100).toFixed(1) + '%'
})

function numDelta(valA, valB, fmt) {
  if (valA == null || valB == null) return '—'
  const d = valB - valA
  const sign = d >= 0 ? '+' : ''
  return sign + fmt(d)
}

const deltaPassRate = computed(() => {
  const l = leftTask.value
  const r = rightTask.value
  if (!l?.completed_items || !r?.completed_items) return '—'
  const d = (r.passed_count / r.completed_items - l.passed_count / l.completed_items) * 100
  return (d >= 0 ? '+' : '') + d.toFixed(1) + '%'
})

const deltaTokens = computed(() => numDelta(
  compareData.value?.left.explicit_metrics?.tokens_total_sum,
  compareData.value?.right.explicit_metrics?.tokens_total_sum,
  v => Math.round(v).toLocaleString()
))

const deltaAvgToken = computed(() => numDelta(
  compareData.value?.left.explicit_metrics?.tokens_avg_per_item,
  compareData.value?.right.explicit_metrics?.tokens_avg_per_item,
  v => v.toFixed(0)
))

const deltaToolRate = computed(() => numDelta(
  compareData.value?.left.explicit_metrics?.tool_success_rate_avg,
  compareData.value?.right.explicit_metrics?.tool_success_rate_avg,
  v => (v * 100).toFixed(1) + '%'
))

const deltaResponseTime = computed(() => numDelta(
  compareData.value?.left.explicit_metrics?.response_time_avg_ms,
  compareData.value?.right.explicit_metrics?.response_time_avg_ms,
  v => (v / 1000).toFixed(1) + ' s'
))

const deltaRagasAR = computed(() => numDelta(
  compareData.value?.left.explicit_metrics?.ragas_answer_relevancy_avg,
  compareData.value?.right.explicit_metrics?.ragas_answer_relevancy_avg,
  v => v.toFixed(3)
))

const deltaRagasFF = computed(() => numDelta(
  compareData.value?.left.explicit_metrics?.ragas_faithfulness_avg,
  compareData.value?.right.explicit_metrics?.ragas_faithfulness_avg,
  v => v.toFixed(3)
))

const deltaJudgeRQ = computed(() => numDelta(
  compareData.value?.left.explicit_metrics?.judge_reasoning_quality_avg,
  compareData.value?.right.explicit_metrics?.judge_reasoning_quality_avg,
  v => v.toFixed(1)
))

const deltaJudgeHS = computed(() => numDelta(
  compareData.value?.left.explicit_metrics?.judge_hallucination_severity_avg,
  compareData.value?.right.explicit_metrics?.judge_hallucination_severity_avg,
  v => v.toFixed(1)
))

const deltaHighRisk = computed(() => {
  const la = compareData.value?.left.explicit_metrics?.security_band_counts?.high
  const rb = compareData.value?.right.explicit_metrics?.security_band_counts?.high
  if (la == null || rb == null) return '—'
  const d = rb - la
  return (d >= 0 ? '+' : '') + d
})

// Δ 色彩：负值在 lowerIsBetter=true 时显示绿色
function deltaClass(dStr, lowerIsBetter = false) {
  if (!dStr || dStr === '—') return ''
  const isPos = dStr.startsWith('+')
  const isNeg = dStr.startsWith('-')
  if (!isPos && !isNeg) return ''
  const good = lowerIsBetter ? isNeg : isPos
  return good ? 'delta-good' : 'delta-bad'
}

// 逐条对齐
const alignedRows = computed(() => {
  if (!compareData.value) return []
  const aItems = compareData.value.left.items || []
  const bItems = compareData.value.right.items || []

  const aMap = new Map()
  const bMap = new Map()
  aItems.forEach(i => aMap.set(i.item_key ?? String(i.item_index), i))
  bItems.forEach(i => bMap.set(i.item_key ?? String(i.item_index), i))

  const keys = [...new Set([...aMap.keys(), ...bMap.keys()])]
  return keys.map(k => ({
    key: k,
    desc: (aMap.get(k) || bMap.get(k))?.description_snapshot?.slice(0, 60) || '',
    a: aMap.get(k) || null,
    b: bMap.get(k) || null,
  }))
})

function rowClass(row) {
  if (!row.a || !row.b) return 'row-unmatched'
  if (row.a.passed === true && row.b.passed === false) return 'row-regress'
  if (row.a.passed === false && row.b.passed === true) return 'row-improve'
  return ''
}

function passSymbol(v) {
  if (v === true) return '✓'
  if (v === false) return '✗'
  return '—'
}

function passClass(v) {
  if (v === true) return 'ok'
  if (v === false) return 'bad'
  return 'muted'
}

function diffLabel(a, b) {
  if (a === b) {
    if (a === true) return '均通过'
    if (a === false) return '均未通过'
    return '均未定'
  }
  if (a === true && b === false) return '▼ 退化'
  if (a === false && b === true) return '▲ 提升'
  return '状态变化'
}

function diffClass(a, b) {
  if (a === b) return a === true ? 'both-ok' : 'both-bad'
  if (a === true && b === false) return 'regress'
  if (a === false && b === true) return 'improve'
  return ''
}

function itemTime(item) {
  if (!item) return '—'
  const sa = item.started_at
  const fa = item.finished_at
  if (!sa || !fa) return '—'
  try {
    return ((new Date(fa) - new Date(sa)) / 1000).toFixed(1) + ' s'
  } catch {
    return '—'
  }
}

// 格式化
function fmtInt(v) { return v != null ? Number(v).toLocaleString() : '—' }
function fmtNum(v, d = 2) { return v != null ? Number(v).toFixed(d) : '—' }
function fmtPct(v) { return v != null ? (v * 100).toFixed(1) + '%' : '—' }
function fmtSec(v) { return v != null ? (v / 1000).toFixed(1) + ' s' : '—' }
function fmtScore10(v) { return v != null ? Number(v).toFixed(1) + '/10' : '—' }
</script>

<style scoped>
.eval-page {
  max-width: 1200px;
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
  margin-bottom: 4px;
  line-height: 1.5;
}

.page-desc code {
  font-size: 11px;
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--bg-surface);
}

.select-row {
  display: flex;
  gap: 14px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  flex: 1;
  min-width: 200px;
}

.field select {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  padding: 8px 10px;
  border-radius: 8px;
}

.banner-error {
  background: color-mix(in srgb, var(--danger) 22%, transparent);
  color: var(--danger);
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
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

/* 汇总表格 */
.summary-grid {
  display: grid;
  grid-template-columns: 220px 1fr 1fr 100px;
  gap: 0;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  font-size: 13px;
}

.summary-col {
  display: flex;
  flex-direction: column;
}

.summary-cell {
  padding: 9px 12px;
  border-bottom: 1px solid var(--border-color);
}

.summary-cell:last-child {
  border-bottom: none;
}

.label-cell {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  font-weight: 600;
  background: var(--bg-primary);
}

.task-a-head {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  color: var(--accent);
  font-weight: 600;
  font-size: 12px;
  text-transform: none;
}

.task-b-head {
  background: color-mix(in srgb, var(--info) 12%, transparent);
  color: var(--info, #7db9e8);
  font-weight: 600;
  font-size: 12px;
  text-transform: none;
}

.delta-col .summary-cell {
  text-align: center;
  font-size: 12px;
  font-family: ui-monospace, monospace;
}

.delta-good { color: var(--success); font-weight: 600; }
.delta-bad  { color: var(--danger);  font-weight: 600; }

/* 逐条对比表 */
.compare-table-wrap {
  overflow-x: auto;
}

.compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.compare-table th,
.compare-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-color);
  text-align: left;
}

.compare-table th {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  background: var(--bg-primary);
}

.col-key { min-width: 80px; }
.col-pass { width: 60px; text-align: center; }
.col-metric { width: 80px; text-align: right; }
.col-sep { width: 20px; text-align: center; color: var(--border-color); }
.col-diff { width: 90px; text-align: center; }

.desc-cell {
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-muted);
  font-size: 11px;
}

.row-regress { background: color-mix(in srgb, var(--danger) 8%, transparent); }
.row-improve { background: color-mix(in srgb, var(--success) 8%, transparent); }
.row-unmatched { opacity: 0.65; }

.ok { color: var(--success); font-weight: 700; }
.bad { color: var(--danger); font-weight: 700; }
.muted { color: var(--text-muted); }

.both-ok { color: var(--success); font-size: 11px; }
.both-bad { color: var(--text-muted); font-size: 11px; }
.regress { color: var(--danger); font-weight: 600; font-size: 11px; }
.improve { color: var(--success); font-weight: 600; font-size: 11px; }

.mono { font-family: ui-monospace, monospace; }
.small { font-size: 11px; }

.hint { font-size: 12px; margin-bottom: 10px; }

.btn {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  border: none;
  cursor: pointer;
  height: fit-content;
  white-space: nowrap;
}

.btn-primary {
  background: var(--accent);
  color: var(--bg-primary);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: 160px 1fr 1fr 80px;
  }
}

@media (max-width: 640px) {
  .select-row {
    flex-direction: column;
  }
  .summary-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
