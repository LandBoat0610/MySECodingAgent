<template>
  <div class="eval-page">
    <section class="metrics-head">
      <div>
        <h2 class="page-title">指标看板</h2>
        <p class="page-desc">
          聚合全部评测任务的显式指标与模糊指标，涵盖效果、性能、安全三个维度。
          选择已完成任务后可加载详细指标；顶部汇总卡片基于所有已完成任务的全量数据。
        </p>
      </div>
      <button type="button" class="btn btn-ghost" @click="refresh">刷新</button>
    </section>

    <!-- 全局汇总卡片 -->
    <div class="metric-grid">
      <div class="metric-card">
        <span class="metric-label">评测任务总数</span>
        <span class="metric-value">{{ ev.tasks.length }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">运行中</span>
        <span class="metric-value accent">{{ running }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">已完成</span>
        <span class="metric-value ok">{{ completedTasks }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">总体通过率</span>
        <span class="metric-value">{{ globalPassRate }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">累计通过 / 未通过</span>
        <span class="metric-value small">{{ totalPassed }} / {{ totalFailed }}</span>
      </div>
    </div>

    <!-- 任务概览表 -->
    <section class="card">
      <h3 class="card-title">任务概览</h3>
      <table class="mini-table">
        <thead>
          <tr>
            <th>任务</th>
            <th>方法</th>
            <th>版本快照</th>
            <th>状态</th>
            <th>通过率</th>
            <th>通过 / 未通过</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in ev.tasks" :key="t.id">
            <td>{{ t.name }}</td>
            <td>{{ methodLabel(t.eval_method) }}</td>
            <td class="mono muted small">{{ t.agent_model_snapshot || '—' }}</td>
            <td><span :class="['pill', t.status]">{{ t.status }}</span></td>
            <td>
              <span v-if="t.total_items > 0">
                {{ passRate(t) }}
                <span class="muted small">（{{ t.completed_items }}/{{ t.total_items }}）</span>
              </span>
              <span v-else class="muted">—</span>
            </td>
            <td>{{ t.passed_count }} / {{ t.failed_count }}</td>
            <td>
              <button
                v-if="t.status === 'completed'"
                class="btn btn-sm btn-ghost"
                :disabled="loadingTaskId === t.id"
                @click="loadTaskDetail(t.id)"
              >
                {{ loadingTaskId === t.id ? '加载中…' : (detailMap[t.id] ? '刷新' : '加载指标') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="ev.tasks.length === 0" class="empty">暂无任务，请在「任务管理」创建。</div>
    </section>

    <!-- 详细指标展开 -->
    <template v-for="t in completedTasksWithDetail" :key="'detail-' + t.id">
      <section class="card detail-card">
        <div class="detail-head">
          <h3 class="card-title">{{ t.name }} · 详细指标</h3>
          <button class="btn-icon-inline" @click="closeDetail(t.id)">×</button>
        </div>

        <!-- 性能维度（显式指标） -->
        <div class="dim-block">
          <h4 class="dim-title">⚡ 性能维度（显式指标）</h4>
          <div class="kpi-grid">
            <div class="kpi">
              <span class="kpi-label">Token 总量</span>
              <strong>{{ fmtInt(detailMap[t.id]?.explicit_metrics?.tokens_total_sum) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">条均 Token</span>
              <strong>{{ fmtNum(detailMap[t.id]?.explicit_metrics?.tokens_avg_per_item) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">提示 Token</span>
              <strong>{{ fmtInt(detailMap[t.id]?.explicit_metrics?.tokens_prompt_sum) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">补全 Token</span>
              <strong>{{ fmtInt(detailMap[t.id]?.explicit_metrics?.tokens_completion_sum) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">LLM 调用总数</span>
              <strong>{{ fmtInt(detailMap[t.id]?.explicit_metrics?.llm_calls_sum) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">条均 LLM 调用</span>
              <strong>{{ fmtNum(detailMap[t.id]?.explicit_metrics?.llm_calls_avg) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">工具成功率（均值）</span>
              <strong>{{ fmtPct(detailMap[t.id]?.explicit_metrics?.tool_success_rate_avg) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">工具均延迟（均值）</span>
              <strong>{{ fmtMs(detailMap[t.id]?.explicit_metrics?.tool_avg_latency_ms_avg) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">平均响应时间</span>
              <strong>{{ fmtSec(detailMap[t.id]?.explicit_metrics?.response_time_avg_ms) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">最长响应时间</span>
              <strong>{{ fmtSec(detailMap[t.id]?.explicit_metrics?.response_time_max_ms) }}</strong>
            </div>
          </div>
        </div>

        <!-- 效果维度（Ragas + Judge） -->
        <div class="dim-block">
          <h4 class="dim-title">🎯 效果维度（模糊指标）</h4>
          <div class="kpi-grid">
            <div class="kpi">
              <span class="kpi-label">任务通过率</span>
              <strong>{{ passRate(t) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">答复相关性（Ragas 均值）</span>
              <strong>{{ fmtNum(detailMap[t.id]?.explicit_metrics?.ragas_answer_relevancy_avg, 3) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">忠实度（Ragas 均值）</span>
              <strong>{{ fmtNum(detailMap[t.id]?.explicit_metrics?.ragas_faithfulness_avg, 3) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">推理质量（Judge 均值）</span>
              <strong>{{ fmtScore10(detailMap[t.id]?.explicit_metrics?.judge_reasoning_quality_avg) }}</strong>
            </div>
            <div class="kpi">
              <span class="kpi-label">幻觉严重度（Judge 均值，低=好）</span>
              <strong>{{ fmtScore10(detailMap[t.id]?.explicit_metrics?.judge_hallucination_severity_avg) }}</strong>
            </div>
          </div>
        </div>

        <!-- 安全维度 -->
        <div class="dim-block">
          <h4 class="dim-title">🔒 安全维度</h4>
          <div class="security-bands">
            <div class="band-item band-low">
              <span class="band-count">{{ secBand(t.id, 'low') }}</span>
              <span class="band-label">低风险</span>
            </div>
            <div class="band-item band-medium">
              <span class="band-count">{{ secBand(t.id, 'medium') }}</span>
              <span class="band-label">中风险</span>
            </div>
            <div class="band-item band-high">
              <span class="band-count">{{ secBand(t.id, 'high') }}</span>
              <span class="band-label">高风险</span>
            </div>
            <div class="band-item band-unknown">
              <span class="band-count">{{ secBand(t.id, 'unknown') }}</span>
              <span class="band-label">未扫描</span>
            </div>
          </div>
        </div>

        <!-- 逐条结果 -->
        <div class="dim-block">
          <h4 class="dim-title">📋 逐条结果</h4>
          <table class="mini-table mini-table-sm">
            <thead>
              <tr>
                <th>#</th>
                <th>通过</th>
                <th>Token</th>
                <th>工具成功率</th>
                <th>耗时(s)</th>
                <th>相关性</th>
                <th>推理质量</th>
                <th>安全等级</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in (detailMap[t.id]?.items || [])" :key="item.item_index">
                <td class="mono muted">{{ item.item_index }}</td>
                <td>
                  <span :class="item.passed === true ? 'ok' : item.passed === false ? 'bad' : 'muted'">
                    {{ item.passed === true ? '✓' : item.passed === false ? '✗' : '—' }}
                  </span>
                </td>
                <td class="mono small">{{ fmtInt(item.runtime_metrics?.tokens_total) }}</td>
                <td class="mono small">{{ fmtPct(item.runtime_metrics?.tool_success_rate) }}</td>
                <td class="mono small">{{ itemResponseTime(item) }}</td>
                <td class="mono small">{{ fmtNum(item.ragas?.answer_relevancy, 2) }}</td>
                <td class="mono small">{{ item.judge?.reasoning_quality != null ? item.judge.reasoning_quality + '/10' : '—' }}</td>
                <td>
                  <span v-if="item.security?.risk_band" :class="['band', item.security.risk_band]">
                    {{ item.security.risk_band }}
                  </span>
                  <span v-else class="muted">—</span>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { useEvaluationStore } from '../../stores/evaluation.js'

const ev = useEvaluationStore()
const detailMap = reactive({})
const loadingTaskId = ref(null)

const running = computed(() =>
  ev.tasks.filter(t => t.status === 'running' || t.status === 'cancelling').length
)
const completedTasks = computed(() => ev.tasks.filter(t => t.status === 'completed').length)
const totalPassed = computed(() => ev.tasks.reduce((a, t) => a + (t.passed_count || 0), 0))
const totalFailed = computed(() => ev.tasks.reduce((a, t) => a + (t.failed_count || 0), 0))

const globalPassRate = computed(() => {
  const totalItems = ev.tasks.reduce((a, t) => a + (t.completed_items || 0), 0)
  if (!totalItems) return '—'
  return ((totalPassed.value / totalItems) * 100).toFixed(1) + '%'
})

const completedTasksWithDetail = computed(() =>
  ev.tasks.filter(t => t.status === 'completed' && detailMap[t.id])
)

onMounted(() => ev.loadTasks())

function refresh() {
  ev.loadTasks()
}

function methodLabel(m) {
  if (m === 'process') return '面向过程'
  if (m === 'combined') return '联合评估'
  return '面向结果'
}

function passRate(t) {
  if (!t.completed_items) return '—'
  return ((t.passed_count / t.completed_items) * 100).toFixed(1) + '%'
}

async function loadTaskDetail(taskId) {
  loadingTaskId.value = taskId
  try {
    const data = await ev.fetchAnalytics(taskId)
    detailMap[taskId] = data
  } catch (e) {
    console.error('loadTaskDetail', e)
  } finally {
    loadingTaskId.value = null
  }
}

function closeDetail(taskId) {
  delete detailMap[taskId]
}

function secBand(taskId, band) {
  return detailMap[taskId]?.explicit_metrics?.security_band_counts?.[band] ?? 0
}

function itemResponseTime(item) {
  const sa = item.started_at
  const fa = item.finished_at
  if (!sa || !fa) return '—'
  try {
    const ms = new Date(fa) - new Date(sa)
    return (ms / 1000).toFixed(1) + ' s'
  } catch {
    return '—'
  }
}

// 格式化函数
function fmtInt(v) {
  if (v == null) return '—'
  return Number(v).toLocaleString()
}

function fmtNum(v, decimals = 2) {
  if (v == null) return '—'
  return Number(v).toFixed(decimals)
}

function fmtPct(v) {
  if (v == null) return '—'
  return (v * 100).toFixed(1) + '%'
}

function fmtMs(v) {
  if (v == null) return '—'
  return Number(v).toFixed(0) + ' ms'
}

function fmtSec(v) {
  if (v == null) return '—'
  return (Number(v) / 1000).toFixed(1) + ' s'
}

function fmtScore10(v) {
  if (v == null) return '—'
  return Number(v).toFixed(1) + ' / 10'
}
</script>

<style scoped>
.eval-page {
  max-width: 1100px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.metrics-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
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
  max-width: 700px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 14px;
}

.metric-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric-label {
  font-size: 12px;
  color: var(--text-muted);
}

.metric-value {
  font-size: 26px;
  font-weight: 700;
}

.metric-value.small {
  font-size: 20px;
}

.metric-value.accent {
  color: var(--accent);
}

.metric-value.ok {
  color: var(--success);
}

.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 18px 20px;
}

.detail-card {
  padding-bottom: 22px;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.btn-icon-inline {
  background: transparent;
  color: var(--text-muted);
  font-size: 18px;
  padding: 2px 6px;
  line-height: 1;
}

.btn-icon-inline:hover {
  color: var(--text-primary);
}

.card-title {
  font-size: 14px;
  font-weight: 600;
}

.dim-block {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.dim-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

.kpi {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.kpi-label {
  font-size: 11px;
  color: var(--text-muted);
}

.kpi strong {
  font-size: 16px;
}

.security-bands {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.band-item {
  border-radius: 10px;
  padding: 12px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 80px;
}

.band-count {
  font-size: 22px;
  font-weight: 700;
}

.band-label {
  font-size: 11px;
}

.band-low {
  background: color-mix(in srgb, var(--success) 18%, transparent);
  color: var(--success);
}

.band-medium {
  background: color-mix(in srgb, var(--warning) 18%, transparent);
  color: var(--warning);
}

.band-high {
  background: color-mix(in srgb, var(--danger) 18%, transparent);
  color: var(--danger);
}

.band-unknown {
  background: var(--bg-tertiary);
  color: var(--text-muted);
}

.mini-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.mini-table-sm {
  font-size: 12px;
}

.mini-table th,
.mini-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-color);
  text-align: left;
}

.mini-table th {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
}

.pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.pill.pending { background: var(--bg-surface); color: var(--text-secondary); }
.pill.running { background: color-mix(in srgb, var(--warning) 35%, transparent); color: var(--warning); }
.pill.completed { background: color-mix(in srgb, var(--success) 35%, transparent); color: var(--success); }
.pill.failed { background: color-mix(in srgb, var(--danger) 35%, transparent); color: var(--danger); }
.pill.cancelled { background: var(--bg-surface); color: var(--text-muted); }
.pill.cancelling { background: color-mix(in srgb, var(--accent) 28%, transparent); color: var(--accent); }

.band {
  text-transform: uppercase;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
}

.band.low { background: color-mix(in srgb, var(--success) 28%, transparent); color: var(--success); }
.band.medium { background: color-mix(in srgb, var(--warning) 28%, transparent); color: var(--warning); }
.band.high { background: color-mix(in srgb, var(--danger) 28%, transparent); color: var(--danger); }

.ok { color: var(--success); font-weight: 700; }
.bad { color: var(--danger); font-weight: 700; }
.muted { color: var(--text-muted); }
.small { font-size: 11px; }
.mono { font-family: ui-monospace, monospace; }

.empty {
  color: var(--text-muted);
  font-size: 13px;
  padding: 12px 0;
}

.btn {
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  border: none;
  cursor: pointer;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.btn-ghost {
  background: var(--bg-surface);
  color: var(--text-secondary);
}

.btn-ghost:hover:not(:disabled) {
  color: var(--text-primary);
}

.btn-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
