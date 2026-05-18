<template>
  <div class="plan-dialog">
    <div class="plan-dialog-header">
      <span>📋 执行计划</span>
      <span class="plan-count">共 {{ store.pendingPlans.length }} 步待确认</span>
    </div>
    <div class="plan-list">
      <div
        v-for="(plan, idx) in store.pendingPlans"
        :key="plan.id"
        class="plan-item"
      >
        <span class="plan-num">{{ idx + 1 }}</span>
        <div class="plan-item-body">
          <div class="plan-item-content">{{ plan.content }}</div>
          <div class="plan-item-meta">
            <span>{{ formatDate(plan.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>
    <div class="plan-dialog-footer">
      <span class="plan-prompt">请确认是否按此计划执行：</span>
      <div v-if="showRefineInput" class="refine-box">
        <textarea
          v-model="refineFeedback"
          rows="3"
          placeholder="告诉 Agent 希望如何修改计划，例如：减少步骤、先检查现有代码、不要改动后端..."
        ></textarea>
      </div>
      <div class="plan-actions">
        <button
          class="btn btn-agree"
          @click="handleAction('agree')"
          :disabled="actionLoading"
        >
          ✅ 同意执行
        </button>
        <button
          class="btn btn-refine"
          @click="handleRefineClick"
          :disabled="actionLoading"
        >
          🔄 {{ showRefineInput ? '提交修改' : '修改计划' }}
        </button>
        <button
          v-if="showRefineInput"
          class="btn btn-cancel-refine"
          @click="cancelRefine"
          :disabled="actionLoading"
        >
          取消
        </button>
        <button
          class="btn btn-skip"
          @click="handleAction('skip')"
          :disabled="actionLoading"
        >
          ⏭ 跳过计划
        </button>
        <button
          class="btn btn-stop"
          @click="handleAction('stop')"
          :disabled="actionLoading"
        >
          ⏹ 终止
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
const showRefineInput = ref(false)
const refineFeedback = ref('')

async function handleAction(action) {
  if (store.pendingPlans.length === 0) return
  actionLoading.value = true
  const plan = store.pendingPlans[0]
  try {
    await store.doPlanAction(plan.id, action)
    // 只刷新计划列表；执行过程由 WebSocket 实时推送，不调 restoreSessionState
    // 避免快照覆盖实时轨迹导致内容突变或重复
    await store.fetchPlans()
  } catch (e) {
    // error handled in store
  } finally {
    actionLoading.value = false
  }
}

async function handleRefineClick() {
  if (!showRefineInput.value) {
    showRefineInput.value = true
    return
  }
  if (store.pendingPlans.length === 0) return
  actionLoading.value = true
  const plan = store.pendingPlans[0]
  try {
    await store.doPlanAction(plan.id, 'refine', refineFeedback.value.trim())
    refineFeedback.value = ''
    showRefineInput.value = false
    await store.fetchPlans()
  } catch (e) {
    // error handled in store
  } finally {
    actionLoading.value = false
  }
}

function cancelRefine() {
  showRefineInput.value = false
  refineFeedback.value = ''
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
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 10px;
  background: var(--bg-tertiary);
  border-radius: 6px;
}

.plan-num {
  font-size: 11px;
  font-weight: 700;
  color: var(--info);
  background: rgba(137, 220, 235, 0.15);
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.plan-item-body { flex: 1; min-width: 0; }

.plan-item-content {
  font-size: 13px;
  line-height: 1.4;
}

.plan-item-meta {
  display: flex;
  align-items: center;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

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
  flex-wrap: wrap;
}

.btn {
  flex: 1 1 120px;
  padding: 7px 0;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.refine-box {
  margin-bottom: 8px;
}

.refine-box textarea {
  width: 100%;
  resize: vertical;
  min-height: 68px;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-primary);
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

.btn-cancel-refine {
  background: var(--bg-surface);
  color: var(--text-secondary);
}

.btn-cancel-refine:hover:not(:disabled) {
  color: var(--text-primary);
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
