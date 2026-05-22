<template>
  <div class="continue-dialog">
    <div class="continue-dialog-header">
      <span>继续执行？</span>
      <span class="continue-badge">已到达当前步骤上限</span>
    </div>
    <div class="continue-dialog-body">
      <div class="continue-title">{{ approval.current_task || '当前步骤' }}</div>
      <div class="continue-detail">
        已执行 {{ approval.current_iteration ?? 0 }} 轮，当前上限为 {{ approval.current_limit ?? 0 }} 轮。
        继续后将增加 {{ approval.additional_iterations ?? 0 }} 轮额度。
      </div>
    </div>
    <div class="continue-dialog-footer">
      <button class="btn btn-continue" :disabled="loading" @click="handleAction('continue')">
        继续
      </button>
      <button class="btn btn-stop-run" :disabled="loading" @click="handleAction('stop')">
        停止
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useAgentStore } from '../stores/agent.js'

const store = useAgentStore()
const loading = ref(false)
const approval = computed(() => store.pendingLoopApproval || {})

async function handleAction(action) {
  if (!approval.value.id) return
  loading.value = true
  try {
    await store.doContinueApproval(approval.value.id, action)
  } catch (e) {
    // handled in store
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.continue-dialog {
  margin: 12px;
  border: 1px solid rgba(137, 180, 250, 0.55);
  border-radius: 10px;
  background: rgba(137, 180, 250, 0.06);
  overflow: hidden;
  flex-shrink: 0;
}
.continue-dialog-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  font-weight: 700;
  color: var(--accent);
  border-bottom: 1px solid rgba(137, 180, 250, 0.18);
}
.continue-badge {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 600;
}
.continue-dialog-body {
  padding: 10px 12px;
}
.continue-title {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
}
.continue-detail {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.45;
}
.continue-dialog-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 10px 12px;
  border-top: 1px solid rgba(137, 180, 250, 0.18);
}
.btn-continue {
  background: var(--accent);
  color: var(--bg-primary);
}
.btn-stop-run {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}
</style>
