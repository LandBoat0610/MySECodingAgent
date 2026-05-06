<template>
  <div class="eval-page">
    <section class="metrics-head">
      <div>
        <h2 class="page-title">指标看板</h2>
        <p class="page-desc">聚合后端持久化的评测任务统计（与 IDE 会话无关）。</p>
      </div>
      <button type="button" class="btn btn-ghost" @click="refresh">刷新</button>
    </section>

    <div class="metric-grid">
      <div class="metric-card">
        <span class="metric-label">评测任务数</span>
        <span class="metric-value">{{ ev.tasks.length }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">运行中</span>
        <span class="metric-value accent">{{ running }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">已完成任务</span>
        <span class="metric-value ok">{{ completedTasks }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">累计用例通过 / 未通过</span>
        <span class="metric-value">{{ totalPassed }} / {{ totalFailed }}</span>
      </div>
    </div>

    <section class="card">
      <h3 class="card-title">任务一览</h3>
      <table class="mini-table">
        <thead>
          <tr>
            <th>任务</th>
            <th>方法</th>
            <th>状态</th>
            <th>通过 / 未通过</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in ev.tasks" :key="t.id">
            <td>{{ t.name }}</td>
            <td>{{ t.eval_method === 'process' ? '面向过程' : '面向结果' }}</td>
            <td>{{ t.status }}</td>
            <td>{{ t.passed_count }} / {{ t.failed_count }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="ev.tasks.length === 0" class="empty">暂无任务，请在「任务管理」创建。</div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useEvaluationStore } from '../../stores/evaluation.js'

const ev = useEvaluationStore()

const running = computed(() =>
  ev.tasks.filter(t => t.status === 'running' || t.status === 'cancelling').length
)
const completedTasks = computed(() => ev.tasks.filter(t => t.status === 'completed').length)
const totalPassed = computed(() => ev.tasks.reduce((a, t) => a + (t.passed_count || 0), 0))
const totalFailed = computed(() => ev.tasks.reduce((a, t) => a + (t.failed_count || 0), 0))

onMounted(() => ev.loadTasks())

function refresh() {
  ev.loadTasks()
}
</script>

<style scoped>
.eval-page {
  max-width: 1000px;
}

.metrics-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 6px;
}

.page-desc {
  font-size: 13px;
  color: var(--text-muted);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 22px;
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

.card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}

.mini-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
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

.empty {
  color: var(--text-muted);
  font-size: 13px;
  padding: 12px 0;
}

.btn {
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
}

.btn-ghost {
  background: var(--bg-surface);
  color: var(--text-secondary);
}
</style>
