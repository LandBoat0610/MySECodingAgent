<template>
  <div class="plan-dialog">
    <div class="plan-dialog-header">
      <span>📋 Execution Plan</span>
      <span class="plan-count">{{ store.pendingPlans.length }} step(s) pending</span>
    </div>
    <div class="plan-list">
      <div
        v-for="plan in store.pendingPlans"
        :key="plan.id"
        class="plan-item"
      >
        <div class="plan-item-content">{{ plan.content }}</div>
        <div class="plan-item-meta">
          <span>{{ formatDate(plan.created_at) }}</span>
          <span :class="['plan-status', plan.status]">{{ plan.status }}</span>
        </div>
      </div>
    </div>
    <div class="plan-dialog-footer">
      <span class="plan-prompt">How would you like to proceed?</span>
      <div class="plan-actions">
        <button
          class="btn btn-agree"
          @click="handleAction('agree')"
          :disabled="actionLoading"
        >
          ✅ Agree
        </button>
        <button
          class="btn btn-refine"
          @click="handleAction('refine')"
          :disabled="actionLoading"
        >
          🔄 Refine
        </button>
        <button
          class="btn btn-skip"
          @click="handleAction('skip')"
          :disabled="actionLoading"
        >
          ⏭ Skip
        </button>
        <button
          class="btn btn-stop"
          @click="handleAction('stop')"
          :disabled="actionLoading"
        >
          ⏹ Stop
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAgentStore } from '../stores/agent.js'

const store = useAgentStore()
const actionLoading = ref(false)

async function handleAction(action) {
  if (store.pendingPlans.length === 0) return
  actionLoading.value = true
  const plan = store.pendingPlans[0]
  try {
    await store.doPlanAction(plan.id, action)
    await store.fetchPlans()
    await store.restoreSessionState()
  } catch (e) {
    // error handled in store
  } finally {
    actionLoading.value = false
  }
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString()
}
</script>

<style scoped>
.plan-dialog {
  margin: 12px;
  border: 1px solid var(--info);
  border-radius: 10px;
  background: rgba(137, 220, 235, 0.05);
  overflow: hidden;
  flex-shrink: 0;
}

.plan-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: rgba(137, 220, 235, 0.1);
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid rgba(137, 220, 235, 0.15);
}

.plan-count {
  font-size: 11px;
  font-weight: 400;
  color: var(--text-muted);
}

.plan-list {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.plan-item {
  padding: 8px 10px;
  background: var(--bg-tertiary);
  border-radius: 6px;
}

.plan-item-content {
  font-size: 13px;
  line-height: 1.4;
}

.plan-item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.plan-status {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  text-transform: uppercase;
}

.plan-status.pending { background: rgba(137, 220, 235, 0.2); color: var(--info); }

.plan-dialog-footer {
  padding: 10px 14px;
  border-top: 1px solid rgba(137, 220, 235, 0.15);
}

.plan-prompt {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.plan-actions {
  display: flex;
  gap: 6px;
}

.btn {
  flex: 1;
  padding: 7px 0;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-agree {
  background: rgba(166, 227, 161, 0.2);
  color: var(--success);
}

.btn-agree:hover:not(:disabled) {
  background: rgba(166, 227, 161, 0.35);
}

.btn-refine {
  background: rgba(137, 180, 250, 0.2);
  color: var(--accent);
}

.btn-refine:hover:not(:disabled) {
  background: rgba(137, 180, 250, 0.35);
}

.btn-skip {
  background: rgba(249, 226, 175, 0.2);
  color: var(--warning);
}

.btn-skip:hover:not(:disabled) {
  background: rgba(249, 226, 175, 0.35);
}

.btn-stop {
  background: rgba(243, 139, 168, 0.2);
  color: var(--danger);
}

.btn-stop:hover:not(:disabled) {
  background: rgba(243, 139, 168, 0.35);
}
</style>
