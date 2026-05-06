<template>
  <div class="eval-page">
    <h2 class="page-title">对比分析</h2>
    <p class="page-desc">选择两次已完成的评测任务，对其逐条通过情况进行并排对比（数据来自后端）。</p>

    <div class="select-row">
      <label class="field">
        <span>基准任务</span>
        <select v-model="leftId" @change="loadSide('left')">
          <option value="">请选择</option>
          <option v-for="t in comparableTasks" :key="'L-' + t.id" :value="t.id">{{ t.name }}（{{ t.passed_count }}/{{ t.failed_count }}）</option>
        </select>
      </label>
      <label class="field">
        <span>对照任务</span>
        <select v-model="rightId" @change="loadSide('right')">
          <option value="">请选择</option>
          <option v-for="t in comparableTasks" :key="'R-' + t.id" :value="t.id">{{ t.name }}（{{ t.passed_count }}/{{ t.failed_count }}）</option>
        </select>
      </label>
    </div>

    <div class="compare-grid">
      <div class="compare-card">
        <h3>基准</h3>
        <ul class="row-list">
          <li v-for="r in leftRows" :key="r.id">
            <span class="idx">#{{ r.item_index }}</span>
            <span :class="r.passed === true ? 'ok' : r.passed === false ? 'bad' : 'muted'">
              {{ r.passed === true ? '通过' : r.passed === false ? '未通过' : '—' }}
            </span>
          </li>
        </ul>
        <div v-if="leftRows.length === 0" class="hint">请选择任务</div>
      </div>
      <div class="compare-card">
        <h3>对照</h3>
        <ul class="row-list">
          <li v-for="r in rightRows" :key="r.id">
            <span class="idx">#{{ r.item_index }}</span>
            <span :class="r.passed === true ? 'ok' : r.passed === false ? 'bad' : 'muted'">
              {{ r.passed === true ? '通过' : r.passed === false ? '未通过' : '—' }}
            </span>
          </li>
        </ul>
        <div v-if="rightRows.length === 0" class="hint">请选择任务</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useEvaluationStore } from '../../stores/evaluation.js'

const ev = useEvaluationStore()

const leftId = ref('')
const rightId = ref('')
const leftRows = ref([])
const rightRows = ref([])

const comparableTasks = computed(() =>
  ev.tasks.filter(t => t.status === 'completed' && (t.completed_items || 0) > 0)
)

onMounted(() => ev.loadTasks())

async function loadSide(side) {
  const id = side === 'left' ? leftId.value : rightId.value
  const target = side === 'left' ? leftRows : rightRows
  if (!id) {
    target.value = []
    return
  }
  try {
    target.value = await ev.fetchResults(id)
  } catch (e) {
    target.value = []
  }
}
</script>

<style scoped>
.eval-page {
  max-width: 960px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 6px;
}

.page-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 18px;
}

.select-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 18px;
}

@media (max-width: 640px) {
  .select-row {
    grid-template-columns: 1fr;
  }
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.field select {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  padding: 8px 10px;
  border-radius: 8px;
}

.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 720px) {
  .compare-grid {
    grid-template-columns: 1fr;
  }
}

.compare-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px 18px;
}

.compare-card h3 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 10px;
}

.row-list {
  list-style: none;
  font-size: 13px;
}

.row-list li {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-color);
}

.idx {
  color: var(--text-muted);
  font-family: ui-monospace, monospace;
}

.ok {
  color: var(--success);
}

.bad {
  color: var(--danger);
}

.muted {
  color: var(--text-muted);
}

.hint {
  font-size: 12px;
  color: var(--text-muted);
  padding: 8px 0;
}
</style>
