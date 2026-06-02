<template>
  <div class="eval-page">
    <div class="results-head">
      <RouterLink :to="{ name: 'eval-tasks' }" class="back-link">← 返回任务列表</RouterLink>
      <h2 class="page-title">评测结果明细：{{ taskId }}</h2>
    </div>

    <LoadingSpinner v-if="loading" text="加载评测结果…" />
    <ErrorBanner v-else-if="loadError" :message="loadError" :dismissible="false" />

    <section v-else class="card">
      <table class="task-table compact">
        <thead>
          <tr>
            <th>#</th>
            <th>通过</th>
            <th>摘要</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td>{{ r.item_index }}</td>
            <td>
              <span :class="r.passed === true ? 'ok' : r.passed === false ? 'bad' : 'muted'">
                {{ r.passed === true ? '是' : r.passed === false ? '否' : '—' }}
              </span>
            </td>
            <td class="mono small">{{ snippet(r.final_answer) }}</td>
            <td class="row-actions tight">
              <button type="button" class="btn btn-sm btn-ghost" @click="selectedReplay = r">回放</button>
            </td>
          </tr>
        </tbody>
      </table>

      <EmptyState
        v-if="rows.length === 0"
        icon="📋"
        title="暂无结果"
        desc="该任务可能尚未完成执行。"
      />

      <div v-if="selectedReplay" class="replay-detail">
        <div class="replay-head">
          <h4>条目 #{{ selectedReplay.item_index }} · 过程溯源</h4>
          <button type="button" class="btn-icon-inline" @click="selectedReplay = null">×</button>
        </div>
        <ol class="trace-flow">
          <li v-for="(step, si) in normalizedTrace(selectedReplay.trace_json)" :key="'st-' + si">
            <div class="step-meta">
              <span class="phase-pill">{{ step.phase }}</span>
              <span class="step-time">{{ step.time }}</span>
            </div>
            <pre v-if="step.state_outline" class="outline">{{ formatJson(step.state_outline) }}</pre>
            <div class="step-body">{{ step.content }}</div>
          </li>
        </ol>
        <p v-if="!normalizedTrace(selectedReplay.trace_json).length" class="muted tiny">暂无轨迹数据。</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { getEvalTaskResults } from '../../api/index.js'
import { LoadingSpinner, ErrorBanner, EmptyState } from '../../components/status/index.js'

const route = useRoute()
const taskId = route.params.taskId
const rows = ref([])
const loading = ref(true)
const loadError = ref('')
const selectedReplay = ref(null)

onMounted(async () => {
  try {
    rows.value = await getEvalTaskResults(taskId)
  } catch (e) {
    loadError.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
})

function snippet(text) {
  const s = text || ''
  return s.length > 160 ? s.slice(0, 160) + '…' : s
}
function normalizedTrace(raw) {
  if (!raw) return []
  return Array.isArray(raw) ? raw : []
}
function formatJson(obj) {
  try { return JSON.stringify(obj, null, 2) } catch { return String(obj) }
}
</script>

<style scoped>
.eval-page { max-width: 900px; }
.results-head { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.back-link { color: var(--text-secondary); text-decoration: none; font-size: 14px; }
.back-link:hover { color: var(--accent); }
.page-title { font-size: 18px; font-weight: 600; }
.ok { color: var(--success); font-weight: 600; }
.bad { color: var(--danger); font-weight: 600; }
.muted { color: var(--text-muted); }
.mono { font-family: ui-monospace, monospace; }
.small { font-size: 13px; }
</style>
